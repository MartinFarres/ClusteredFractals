import os
import redis
import time
from kubernetes import client, config
from kubernetes.stream import stream
import json

# Kubernetes setup
config.load_incluster_config()  

v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()

# Redis setup
redis_host = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=redis_host, port=6379, db=0)

# Dinamic Namespace
NAMESPACE = os.getenv("POD_NAMESPACE", "default")

# Constants
STATEFULSET_NAME = "mpi-node"
NODE_COUNT = 4  # Fixed number of MPI nodes

def get_current_node_count():
    """Get the current replica count of the StatefulSet."""
    statefulset = apps_v1.read_namespaced_stateful_set(name=STATEFULSET_NAME, namespace=NAMESPACE)
    return statefulset.spec.replicas

def scale_mpi_nodes():
    """Scale the StatefulSet to the desired number of nodes (once)."""
    current_count = get_current_node_count()
    if current_count != NODE_COUNT:
        apps_v1.patch_namespaced_stateful_set_scale(
            name=STATEFULSET_NAME,
            namespace=NAMESPACE,
            body={"spec": {"replicas": NODE_COUNT}}
        )
        print(f"Scaled StatefulSet to {NODE_COUNT} replicas.")
    else:
        print(f"StatefulSet already has {NODE_COUNT} replicas.")

def wait_for_all_nodes_ready():
    """Wait until all MPI nodes are in the 'Running' state."""
    print("Waiting for all MPI nodes to be ready...")
    while True:
        pods = v1.list_namespaced_pod(namespace=NAMESPACE, label_selector="app=mpi-node").items
        ready = [p for p in pods if p.status.phase == "Running" and all(cs.ready for cs in p.status.container_statuses)]
        if len(ready) == NODE_COUNT:
            return sorted(ready, key=lambda p: p.metadata.name)
        print(f"Ready: {len(ready)}/{NODE_COUNT}")
        time.sleep(2)

def get_mpi_host_list(pods):
    """Generate the MPI host list (DNS names of pods)."""
    return ",".join(f"{p.metadata.name}.{STATEFULSET_NAME}.{NAMESPACE}.svc.cluster.local" for p in pods)

def run_mpi_on_master(master_pod, host_list, args):
    """Run MPI job on the master node."""
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
    """Main loop for pulling jobs from Redis and running them."""
    print("Puller started. Listening for jobs in Redis...")
    while True:
        job = r.lpop("mpi_jobs")
        if job:
            print("Received job:", job)
            try:
                data = json.loads(job)
                args = data.get("args", [])
                
                # Scale nodes only once
                scale_mpi_nodes()

                # Wait for all nodes to be ready
                pods = wait_for_all_nodes_ready()

                # Get the master pod and host list for MPI
                master = pods[0].metadata.name
                host_list = get_mpi_host_list(pods)

                # Run the job on the master node (no response expected)
                run_mpi_on_master(master, host_list, args)
            except Exception as e:
                print(f"Error processing job: {e}")
        else:
            time.sleep(1)

if __name__ == "__main__":
    main_loop()
