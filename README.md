# ClusteredFractals

ClusteredFractals is a distributed fractal‐generation system built on MPI and Kubernetes. It lets you run high‐performance fractal calculations across a cluster of pods.

---

## 📖 Table of Contents

- [ClusteredFractals](#clusteredfractals)
  - [📖 Table of Contents](#-table-of-contents)
  - [Architecture Overview](#architecture-overview)
  - [Local Development](#local-development)
  - [Kubernetes Deployment](#kubernetes-deployment)
    - [**Prerequisites**](#prerequisites)
    - [**Steps**](#steps)
    - [**Environment \& Configuration**](#environment--configuration)
    - [**Submitting MPI Jobs**](#submitting-mpi-jobs)
    - [**Load test script**](#load-test-script)
    - [**Job Payload Format**](#job-payload-format)

---

## Architecture Overview

![image](https://github.com/user-attachments/assets/b0f000c0-4c41-40b0-8a07-ba219fb09a96)


1. **Client** submits fractal parameters via REST to the **Server**.
2. **Server:** 

   - Queues jobs in Redis (`pending_tasks`) using `RPUSH mpi_jobs...`.

   - Allows the client to retrieve the image once it's ready (`completed_tasks[uuid]`).
3. **Puller:** 

   Watches Redis and uses the Kubernetes API to:

    - Ensure the MPI StatefulSet (headless service + pods) is deployed

    - Wait for pods to become ready

    - Ensure the Observer is deployed

    - Wait for the Observer to become ready

    - Generate a hostfile and distribute SSH keys

    - Invoke `mpirun` on the master pod

4. **Observer:**

   - Monitors the master pod logs

   - Looks for special events in the logs (`[TASK]`, `[STATUS]`, `[SUCCESS]`, `[ERROR]`)

   - Updates the task status in Redis (`running_tasks`) as `"fail"` or `"success"`

5. **Autoscaler:**

   - Dynamically scales Kubernetes namespaces based on the ratio of pending tasks to active namespaces

   - Deploys new namespaces if the task load is high (`ratio > THRESHOLD`), or deletes the last namespace if load is low and more than one namespace exists

   - Monitors task statuses in Redis (`running_tasks`):

      - If a task succeeded → removes it from the queue

      - If a task failed → re-queues it into `pending_tasks` and redeploys its namespace

6. The MPI C++ binary runs, writes out `fractal.png`, and exits.

---

## Local Development

1. **Install dependencies**
   ```bash
   make install
   ```
2. **Run Server & Client together**

   ```bash
   make dev
   ```

3. **Or run separately**

   ```bash
   make run-server   # backend
   make run-client   # frontend
   ```

4. **Clean artifacts**

   ```bash
   make clean
   ```

---

## Kubernetes Deployment

### **Prerequisites**

- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Minikube](https://minikube.sigs.k8s.io/docs/) for local testing

### **Steps**

```bash
# Start a local cluster
minikube start

# Deploy all components
kubectl apply -k manifests/

# To tear down
kubectl delete -k manifests/
minikube stop

#OPTIONAL:
# See namespaces
kubectl get namespaces

# Monitor pods
watch kubectl get pods -n <namespace-name>

# Monitor logs 
kubectl logs -f <pod-name> -n <namespace-name>

# Monitor pods, services, deployments, etc
kubectl get all -n <namespace-name>
```

### **Environment & Configuration**

The Puller Deployment expects these env vars:

```yaml
- name: REDIS_HOST # Redis service DNS
  value: redis
- name: POD_NAMESPACE # usually injected via downward API
- name: MPI_IMAGE # your mpi-node image
- name: MPIPASS # SSH password for mpi-user
- name: NODE_COUNT # number of replicas
  value: "4"
- name: SLOTS_PER_NODE # slots per node for mpirun
  value: "2"
- name: OBSERVER_DEPLOYMENT_NAME # name of the observer Deployment
  value: observer
- name: OBSERVER_IMAGE # image for the observer
- name: OBSERVER_REPLICAS # number of observer replicas
  value: "1"

```

### **Submitting MPI Jobs**

After Redis is running:

```bash
# Enter the redis pod
kubectl exec -it <redis-pod-name> -n distributed-fractals deploy/redis -- redis-cli
```

Inside the redis:

```bash
# Push a job
RPUSH pending_tasks '{"args":[<args>]}'
```
```bash
# Check the length of the pending_tasks or running_tasks queues
LRANGE <queue_name> 0 -1
```

### **Load test script**

This script (stress_test.sh) sends multiple PUT requests to the /api/submit-job endpoint to verify that the server is working correctly.

It simulates light load by allowing you to adjust the number of requests and the concurrency level. It prints the HTTP status code for each request.

Usage

```bash
#<IP or hostname>: The address of the server
#[PORT]: (Optional) defaults to 30080 if not specified
./stress_test.sh <IP or hostname> [PORT]
```

Expected Output

The script prints one line per request with the HTTP response code (200, 202, 404, etc.).
If you see 000, it means the connection failed (likely due to server not running, wrong port, or networking issue).

### **Job Payload Format**

| Field  | Type    | Description                               |
| ------ | ------- | ----------------------------------------- |
| `args` | `array` | Command‑line arguments to pass to fractal |

**Example**: generate a 1024×1024 fractal with 500 iterations

```bash
RPUSH mpi_jobs '{
  "args":[
    "--width", "1024",
    "--height", "1024",
    "--iterations", "500",
    "--output", "fractal.png"
  ]
}'
```

For more details on available arguments, see the C++ README: https://github.com/FrancoYudica/DistributedFractals/issues
