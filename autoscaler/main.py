import os
import redis
import time
import tempfile
import json
from kubernetes import client, config, utils
from kubernetes.client import ApiException

# --- AutoScaling constants ---
THRESHOLD        = float(os.getenv("SCALING_THRESHOLD", 10.0))
NAMESPACE_PREFIX = "ds-clmpi"
MANIFEST_DIR     = "/manifests"   # <-- montado desde el ConfigMap

# --- Redis setup ---
redis_host = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(host=redis_host, port=6379, db=0)

# --- Kubernetes setup ---
config.load_incluster_config()
k8s_client = client.ApiClient()
core_v1    = client.CoreV1Api()


def list_namespaces():
    return sorted(
        ns.metadata.name 
        for ns in core_v1.list_namespace().items
        if ns.metadata.name.startswith(NAMESPACE_PREFIX)
    )


def deploy_namespace(ns_name: str):
    print(f"[Autoscaler] Creating namespace: {ns_name}")
    try:
        core_v1.create_namespace(client.V1Namespace(
            metadata=client.V1ObjectMeta(name=ns_name)
        ))
    except ApiException as e:
        if e.status != 409:
            raise

    ordered_manifests = [
        "puller-sa.yaml",
        "puller-role.yaml",
        "puller-rolebinding.yaml",
        "puller-deployment.yaml"
    ]

    for fname in ordered_manifests:
        path = os.path.join(MANIFEST_DIR, fname)
        if not os.path.exists(path):
            continue

        with open(path) as f:
            content = f.read()

        content = content.replace(
            "namespace: PLACE_HOLDER",
            f"namespace: {ns_name}"
        )

        with tempfile.NamedTemporaryFile("w+", suffix=".yaml") as tmp:
            tmp.write(content)
            tmp.flush()
            utils.create_from_yaml(
                k8s_client,
                tmp.name,
                namespace=ns_name
            )
        print(f"  ↳ Applied {fname} → {ns_name}")


def delete_namespace(ns_name: str):
    print(f"[Autoscaler] Deleting namespace: {ns_name}")
    core_v1.delete_namespace(name=ns_name)


def get_pending_tasks_len() -> int:
    return r.llen("pending_tasks")


def get_running_tasks():
    return r.lrange("running_tasks", 0, -1)


def auto_scaling():
    pending_tasks_len = get_pending_tasks_len()
    namespaces = list_namespaces()
    count = len(namespaces)
    ratio = (pending_tasks_len / count) if count else pending_tasks_len

    print(f"[Autoscaler] tasks={pending_tasks_len}, namespaces={count}, ratio={ratio:.2f}")

    if ratio > THRESHOLD:
        new_ns = f"{NAMESPACE_PREFIX}{count+1}"
        deploy_namespace(new_ns)

    elif ratio < THRESHOLD and count > 1:
        last_ns = namespaces[-1]
        delete_namespace(last_ns)


def tasks_status_check():
    running_tasks = get_running_tasks()

    for task_data in running_tasks:
        try:
            task = json.loads(task_data.decode('utf-8'))
            status = task.get("status")
            namespace = task.get("namespace")

            if status == "success":
                r.lrem("running_tasks", 0, task_data)
                print(f"[Status] Task success, removed: {task}")

            elif status == "fail":
                r.lrem("running_tasks", 0, task_data)
                # push into pending_tasks
                r.rpush("pending_tasks", json.dumps(task))
                if namespace:
                    print(f"[Status] Task failed in {namespace}. Redeploying...")
                    delete_namespace(namespace)
                    # wait until deletion completes
                    while namespace in list_namespaces():
                        time.sleep(1)
                    deploy_namespace(namespace)
                else:
                    print(f"[Status] Failed task without namespace: {task}")

        except (json.JSONDecodeError, AttributeError) as e:
            print(f"[Error] Couldn't process task: {task_data}. Error: {e}")


def main_loop():
    namespaces = list_namespaces()
    if not namespaces:
        print("[Autoscaler] No namespaces found, creating initial namespace")
        deploy_namespace(f"{NAMESPACE_PREFIX}1")

    while True:
        auto_scaling()
        tasks_status_check()
        time.sleep(2)


if __name__ == "__main__":
    main_loop()
