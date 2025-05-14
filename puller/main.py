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
NODE_COUNT = int(os.getenv("NODE_COUNT", 4))  
SLOTS_PER_NODE = int(os.getenv("SLOTS_PER_NODE", 2)) 
IMAGE = os.getenv("MPI_IMAGE")
MPIPASS = os.getenv("MPIPASS")

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
    env_vars = [client.V1EnvVar(name="MPIPASS", value=MPIPASS)]
    container = client.V1Container(
        name="mpi-node",
        image=IMAGE,
        image_pull_policy="Always",
        env=env_vars,
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
        print(f"StatefulSet created with {NODE_COUNT} replicas.")
    except ApiException as e:
        if e.status == 409:
            print("StatefulSet already exists.")
        else:
            print(f"StatefulSet creation error: {e.status} {e.body}")
            raise

# Ensure headless Service and StatefulSet exist with correct replica count
def ensure_mpi_deployed():
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

# Wait until all MPI nodes are in the 'Running'
def wait_for_all_nodes_ready():
    print("Waiting for all MPI nodes to be ready...")
    while True:
        pods = v1.list_namespaced_pod(namespace=NAMESPACE, label_selector=f"app={STATEFULSET_NAME}").items
        ready = [p for p in pods if p.status.phase == "Running" and all(cs.ready for cs in p.status.container_statuses)]
        if len(ready) == NODE_COUNT:
            return sorted(ready, key=lambda p: p.metadata.name)
        print(f"Ready: {len(ready)}/{NODE_COUNT}")
        time.sleep(2)

# Create hostfile and share SSH keys across nodes
def prepare_hostfile_and_keys(master_pod, pods):
    # Paths inside the container
    project_root = "/home/mpi-user/fractal/DistributedFractals"
    build_dir = f"{project_root}/build"
    hostfile_path = f"{build_dir}/hostfile"

    # Build hostfile content
    lines = [f"{p.status.pod_ip} slots={SLOTS_PER_NODE}\n" for p in pods]
    hostfile_content = "".join(lines)

    # Ensure build directory exists and write hostfile
    cmd_write = f"mkdir -p {build_dir} && echo -e '{hostfile_content}' > {hostfile_path}"
    print(f"Writing hostfile to {hostfile_path}:{hostfile_content}")
    stream(v1.connect_get_namespaced_pod_exec,
           name=master_pod, namespace=NAMESPACE,
           command=["/bin/bash","-c", cmd_write],
           stderr=True, stdin=False, stdout=True, tty=False)

    # Share public keys using the script in src/scripts
    script_path = f"{project_root}/src/scripts/share_public_keys.sh"
    cmd_keys = f"bash {script_path} {hostfile_path} {MPIPASS}"
    print(f"Sharing public keys with: {cmd_keys}")
    stream(v1.connect_get_namespaced_pod_exec,
           name=master_pod, namespace=NAMESPACE,
           command=["/bin/bash","-c", cmd_keys],
           stderr=True, stdin=False, stdout=True, tty=False)

# Return the ClusterIp of the 'server' Service in our namespace
def get_server_service_ip():
    try:
        svc = v1.read_namespaced_service(name="server", namespace=NAMESPACE)
        ip = svc.spec.cluster_ip
        return ip
    except ApiException as e:
        print(f"Error reading server service: {e.status} {e.body}")
        raise


# Prepare environment then run the MPI job
def run_mpi_on_master(master_pod, pods, args):
    # Prepare hostfile and distribute keys
    prepare_hostfile_and_keys(master_pod, pods)
    # MPI run
    project_root = "/home/mpi-user/fractal/DistributedFractals/build"
    total_slots = NODE_COUNT * SLOTS_PER_NODE
    mpi_cmd = f"mpirun -np {total_slots} --hostfile {project_root}/hostfile {project_root}/fractal_mpi  {' '.join(args)} -on {get_server_service_ip()} 5001"
    print(f"Running MPI command: {mpi_cmd}")
    output = stream(v1.connect_get_namespaced_pod_exec,
       name=master_pod, namespace=NAMESPACE,
       command=["/bin/bash", "-l", "-c", mpi_cmd],
       stderr=True, stdin=False, stdout=True, tty=False)
    print(output)
    print("MPI job initiated.")


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
                # Run the full MPI workflow on master
                run_mpi_on_master(master, pods, args)
            except Exception as e:
                print(f"Error processing job: {e}")
        else:
            time.sleep(1)

if __name__ == "__main__":
    main_loop()
