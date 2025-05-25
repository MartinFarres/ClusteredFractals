import os
import redis
import time
import tempfile
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

    # Aplica cada YAML en /manifests al namespace ns_name
    for fname in os.listdir(MANIFEST_DIR):
        
        if not fname.endswith((".yaml", ".yml")):
            continue
        path = os.path.join(MANIFEST_DIR, fname)
        
        # Leer y parchear namespace en el manifiesto
        with open(path) as f:
            content = f.read()
        
        # Si en los archivos viene un namespace fijo, lo reemplazamos:
        content = content.replace(
            "namespace: PLACE_HOLDER",
            f"namespace: {ns_name}"
        )

        # Crear un archivo temporal para utils.create_from_yaml
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
    core_v1.delete_namespace(ns_name)

def get_pending_jobs() -> int:
    return r.llen("pending_jobs")

def main_loop():
    namespaces = list_namespaces()
    if not namespaces:
        print("[Autoscaler] No hay namespaces, creando DS-CLMPI1 de arranque")
        deploy_namespace(f"{NAMESPACE_PREFIX}1")
        namespaces = list_namespaces()
    
    while True:
        jobs       = get_pending_jobs()
        namespaces = list_namespaces()
        count      = len(namespaces)
        ratio      = (jobs / count) if count else jobs

        print(f"[Autoscaler] jobs={jobs}, namespaces={count}, ratio={ratio:.2f}")

        if ratio > THRESHOLD:
            # Scale up
            new_ns = f"{NAMESPACE_PREFIX}{count+1}"
            deploy_namespace(new_ns)

        elif ratio < THRESHOLD and count > 1:
            # Scale down
            last_ns = namespaces[-1]
            delete_namespace(last_ns)

        time.sleep(10)

if __name__ == "__main__":
    main_loop()
