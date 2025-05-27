import os
import redis
import time
import json
from kubernetes import client, config
from kubernetes.stream import stream
from kubernetes.client.rest import ApiException

# --- Kubernetes setup ---
config.load_incluster_config()
v1      = client.CoreV1Api()
apps_v1 = client.AppsV1Api()

# --- Redis setup ---
redis_host = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(host=redis_host, port=6379, db=0)

# --- Dynamic Namespace from env ---
NAMESPACE = os.getenv("POD_NAMESPACE")

# --- MPI‐nodes constants ---
STATEFULSET_NAME = "mpi-node"
SERVICE_NAME     = "mpi-node-headless"
NODE_COUNT       = int(os.getenv("NODE_COUNT", 4))
SLOTS_PER_NODE   = int(os.getenv("SLOTS_PER_NODE", 2))
IMAGE            = os.getenv("MPI_IMAGE")
MPIPASS          = os.getenv("MPIPASS")

# --- Observer constants ---
OBSERVER_DEPLOYMENT = os.getenv("OBSERVER_DEPLOYMENT_NAME", "observer")
OBSERVER_IMAGE      = os.getenv("OBSERVER_IMAGE")
OBSERVER_REPLICAS   = int(os.getenv("OBSERVER_REPLICAS", 1))

# --- MPI‐nodes: Service + StatefulSet generators ---
def create_headless_service():
    svc = client.V1Service(
        metadata=client.V1ObjectMeta(name=SERVICE_NAME),
        spec=client.V1ServiceSpec(
            cluster_ip='None',
            selector={"app": STATEFULSET_NAME},
            ports=[client.V1ServicePort(port=22, name="ssh")]
        )
    )
    try:
        v1.create_namespaced_service(namespace=NAMESPACE, body=svc)
        print("Headless service created.")
    except ApiException as e:
        if e.status != 409:
            raise

def create_statefulset():
    env_vars = [client.V1EnvVar(name="MPIPASS", value=MPIPASS)]
    container = client.V1Container(
        name="mpi-node",
        image=IMAGE,
        image_pull_policy="Always",
        env=env_vars,
        ports=[client.V1ContainerPort(container_port=22)]
    )
    spec = client.V1StatefulSetSpec(
        service_name=SERVICE_NAME,
        selector=client.V1LabelSelector(match_labels={"app": STATEFULSET_NAME}),
        replicas=NODE_COUNT,
        template=client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": STATEFULSET_NAME}),
            spec=client.V1PodSpec(containers=[container])
        )
    )
    sts = client.V1StatefulSet(
        metadata=client.V1ObjectMeta(name=STATEFULSET_NAME),
        spec=spec
    )
    try:
        apps_v1.create_namespaced_stateful_set(namespace=NAMESPACE, body=sts)
        print(f"StatefulSet '{STATEFULSET_NAME}' created.")
    except ApiException as e:
        if e.status != 409:
            raise

def ensure_mpi_deployed():
    try:
        sts = apps_v1.read_namespaced_stateful_set(STATEFULSET_NAME, NAMESPACE)
        if sts.spec.replicas != NODE_COUNT:
            apps_v1.patch_namespaced_stateful_set_scale(
                STATEFULSET_NAME, NAMESPACE, {"spec": {"replicas": NODE_COUNT}}
            )
            print(f"Scaled MPI StatefulSet → {NODE_COUNT}")
        else:
            print(f"MPI StatefulSet already at {NODE_COUNT} replicas.")
    except ApiException as e:
        if e.status == 404:
            create_headless_service()
            create_statefulset()
        else:
            raise

def wait_for_all_nodes_ready():
    print("🔎 Waiting for MPI nodes...")
    while True:
        pods = v1.list_namespaced_pod(NAMESPACE, label_selector=f"app={STATEFULSET_NAME}").items
        ready = [p for p in pods
                 if p.status.phase == "Running"
                 and all(cs.ready for cs in p.status.container_statuses)]
        print(f"  {len(ready)}/{NODE_COUNT} MPI nodes ready")
        if len(ready) == NODE_COUNT:
            return sorted(ready, key=lambda p: p.metadata.name)
        time.sleep(2)

# --- Observer Deployment generator & scaler ---
def create_observer_deployment(master_pod_name):
    env_vars = [client.V1EnvVar(name="REDIS_HOST", value=redis_host), 
                client.V1EnvVar(name="POD_NAMESPACE", value=NAMESPACE), 
                client.V1EnvVar(name="MASTER_POD", value=master_pod_name)]
    container = client.V1Container(
        name="observer",
        image=OBSERVER_IMAGE,
        image_pull_policy="Always",
        env=env_vars,
        ports=[client.V1ContainerPort(container_port=8080)]
    )
    spec = client.V1DeploymentSpec(
        replicas=OBSERVER_REPLICAS,
        selector=client.V1LabelSelector(match_labels={"app": OBSERVER_DEPLOYMENT}),
        template=client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": OBSERVER_DEPLOYMENT}),
            spec=client.V1PodSpec(containers=[container])
        )
    )
    deploy = client.V1Deployment(
        metadata=client.V1ObjectMeta(name=OBSERVER_DEPLOYMENT),
        spec=spec
    )
    try:
        apps_v1.create_namespaced_deployment(namespace=NAMESPACE, body=deploy)
        print(f"Observer Deployment '{OBSERVER_DEPLOYMENT}' created.")
    except ApiException as e:
        if e.status != 409:
            raise

def ensure_observer_deployed(master_pod_name):
    try:
        dep = apps_v1.read_namespaced_deployment(OBSERVER_DEPLOYMENT, NAMESPACE)
        if dep.spec.replicas != OBSERVER_REPLICAS:
            apps_v1.patch_namespaced_deployment_scale(
                OBSERVER_DEPLOYMENT, NAMESPACE, {"spec": {"replicas": OBSERVER_REPLICAS}}
            )
            print(f"Scaled Observer → {OBSERVER_REPLICAS}")
        else:
            print(f"Observer already at {OBSERVER_REPLICAS} replicas.")
    except ApiException as e:
        if e.status == 404:
            create_observer_deployment(master_pod_name)
        else:
            raise

def wait_for_observer_ready():
    print("🔎 Waiting for Observer...")
    while True:
        pods = v1.list_namespaced_pod(NAMESPACE, label_selector=f"app={OBSERVER_DEPLOYMENT}").items
        ready = [p for p in pods
                 if p.status.phase == "Running"
                 and all(cs.ready for cs in p.status.container_statuses)]
        if len(ready) >= OBSERVER_REPLICAS:
            print("Observer is ready.")
            return
        time.sleep(2)

# --- Helpers for MPI run ---
def prepare_hostfile_and_keys(master_pod, pods):
    project_root   = "/home/mpi-user/fractal/DistributedFractals"
    build_dir      = f"{project_root}/build"
    hostfile_path  = f"{build_dir}/hostfile"
    lines = [f"{p.status.pod_ip} slots={SLOTS_PER_NODE}\n" for p in pods]
    hostfile_content = "".join(lines)

    cmd_write = f"mkdir -p {build_dir} && echo -e '{hostfile_content}' > {hostfile_path}"
    stream(v1.connect_get_namespaced_pod_exec,
           name=master_pod, namespace=NAMESPACE,
           command=["/bin/bash", "-c", cmd_write],
           stderr=True, stdin=False, stdout=True, tty=False)

    script_path = f"{project_root}/src/scripts/share_public_keys.sh"
    cmd_keys = f"bash {script_path} {hostfile_path} {MPIPASS}"
    stream(v1.connect_get_namespaced_pod_exec,
           name=master_pod, namespace=NAMESPACE,
           command=["/bin/bash", "-c", cmd_keys],
           stderr=True, stdin=False, stdout=True, tty=False)


def run_mpi_on_master(master_pod, pods, args, job_uuid):
    prepare_hostfile_and_keys(master_pod, pods)

    project_root = "/home/mpi-user/fractal/DistributedFractals/build"
    total_slots  = NODE_COUNT * SLOTS_PER_NODE
    mpi_cmd = (
        f"mpirun -np {total_slots} "
        f"--hostfile {project_root}/hostfile "
        f"{project_root}/fractal_mpi "
        
        # Output Network Settings
        f"{' '.join(args)} -on 0.0.0.0 5001 {job_uuid}"
    )
    print(f"Running MPI command: {mpi_cmd}")

    run_and_check_cmd = f"python3 /home/mpi-user/run_and_check.py {mpi_cmd}"

    output = stream(v1.connect_get_namespaced_pod_exec,
           name=master_pod, namespace=NAMESPACE,
           command=["/bin/bash", "-l", "-c", run_and_check_cmd],
           stderr=True, stdin=False, stdout=True, tty=False)
    print(output)
    print("MPI job initiated.")

def build_mpi_args(data):
    args = []
    flags = [
        ("--width",      "width"),
        ("--height",     "height"),
        ("--block_size", "block_size"),
        ("--samples",    "samples"),
        ("--zoom",       "zoom"),
        ("--camera_x",   "camera_x"),
        ("--camera_y",   "camera_y"),
        ("--type",       "type"),
        ("--color_mode", "color_mode"),
    ]
    for flag, key in flags:
        if key in data:
            args.extend([flag, str(data[key])])
    return args

# --- Main loop ---
def main_loop():
    print("Puller started. Listening for tasks in Redis…")
    while True:
        job = r.lpop("pending_tasks")
        if not job:
            time.sleep(1)
            continue

        print("Received job:", job)
        data     = json.loads(job)
        job_uuid = data.pop("uuid", None)

        # Añadir campos status y namespace
        data["status"]     = ""
        data["namespace"] = NAMESPACE

        # Push a running_task
        r.lpush("running_tasks", json.dumps(data))
        print("Pushed to running_task.")

        # Build MPI args
        filtered = {k: v for k, v in data.items() if k not in ["status", "namespace"]}
        mpi_args = build_mpi_args(filtered)

        # 1) Asegurar MPI‐nodes
        ensure_mpi_deployed()
        mpi_pods = wait_for_all_nodes_ready()

        # 2) Asegurar Observer
        ensure_observer_deployed(mpi_pods[0].metadata.name)
        wait_for_observer_ready()

        # 3) Ejecutar MPI
        run_mpi_on_master(mpi_pods[0].metadata.name, mpi_pods, mpi_args, job_uuid)

if __name__ == "__main__":
    main_loop()
