import os
import redis
import time
import json
from kubernetes import client, config
from kubernetes.stream import stream
from kubernetes.client.rest import ApiException

# Kubernetes setup
config.load_incluster_config()
v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()

# Redis setup
redis_host = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=redis_host, port=6379, db=0)

# Dynamic Namespace
NAMESPACE = os.getenv("POD_NAMESPACE", "default")

# Constants
STATEFULSET_NAME = "mpi-node"
SERVICE_NAME = "mpi-node-headless"
NODE_COUNT = 4  # Fixed number of MPI nodes
IMAGE = os.getenv("MPI_IMAGE", "your-registry/mpi-node:latest")

# Manifest generators
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
        if e.status == 409:
            print("Headless service already exists.")
        else:
            print(f"Service creation error: {e.status} {e.body}")
            raise


def create_statefulset():
    container = client.V1Container(
        name="mpi-node",
        image=IMAGE,
        ports=[client.V1ContainerPort(container_port=22)],
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
        print("StatefulSet created with ", NODE_COUNT, " replicas.")
    except ApiException as e:
        if e.status == 409:
            print("StatefulSet already exists.")
        else:
            print(f"StatefulSet creation error: {e.status} {e.body}")
            raise


def ensure_mpi_deployed():
    """Ensure headless Service and StatefulSet exist with correct replica count."""
    try:
        sts = apps_v1.read_namespaced_stateful_set(name=STATEFULSET_NAME, namespace=NAMESPACE)
        current = sts.spec.replicas
        if current != NODE_COUNT:
            apps_v1.patch_namespaced_stateful_set_scale(
                name=STATEFULSET_NAME,
                namespace=NAMESPACE,
                body={"spec": {"replicas": NODE_COUNT}}
            )
            print(f"Scaled StatefulSet from {current} to {NODE_COUNT} replicas.")
        else:
            print(f"StatefulSet present with {current} replicas.")
    except ApiException as e:
        if e.status == 404:
            create_headless_service()
            create_statefulset()
        else:
            print(f"Error checking StatefulSet: {e.status} {e.body}")
            raise


def wait_for_all_nodes_ready():
    """Wait until all MPI nodes are in the 'Running' & ready state."""
    print("Waiting for all MPI nodes to be ready...")
    while True:
        pods = v1.list_namespaced_pod(namespace=NAMESPACE, label_selector=f"app={STATEFULSET_NAME}").items
        ready = [p for p in pods if p.status.phase == "Running" and all(cs.ready for cs in p.status.container_statuses)]
        if len(ready) == NODE_COUNT:
            return sorted(ready, key=lambda p: p.metadata.name)
        print(f"Ready: {len(ready)}/{NODE_COUNT}")
        time.sleep(2)


def get_mpi_host_list(pods):
    return ",".join(f"{p.metadata.name}.{SERVICE_NAME}.{NAMESPACE}.svc.cluster.local" for p in pods)


def run_mpi_on_master(master_pod, host_list, args):
    mpi_cmd = f"mpiexec -n {NODE_COUNT} -host {host_list} ./fractal {' '.join(args)}"
    print(f"Running command on master: {mpi_cmd}")

    exec_command = ["/bin/bash", "-c", mpi_cmd]
    stream(v1.connect_get_namespaced_pod_exec,
           name=master_pod,
           namespace=NAMESPACE,
           command=exec_command,
           stderr=True, stdin=False, stdout=True, tty=False)
    print("MPI job sent to master node.")


def main_loop():
    print("Puller started. Listening for jobs in Redis...")
    while True:
        job = r.lpop("mpi_jobs")
        if job:
            print("Received job:", job)
            try:
                data = json.loads(job)
                args = data.get("args", [])

                # Ensure the MPI deployment exists and is scaled
                ensure_mpi_deployed()

                # Wait for all pods to be ready before running
                pods = wait_for_all_nodes_ready()

                master = pods[0].metadata.name
                host_list = get_mpi_host_list(pods)

                run_mpi_on_master(master, host_list, args)
            except Exception as e:
                print(f"Error processing job: {e}")
        else:
            time.sleep(1)

if __name__ == "__main__":
    main_loop()
