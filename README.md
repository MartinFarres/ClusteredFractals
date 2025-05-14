# ClusteredFractals

ClusteredFractals is a distributed fractal‐generation system built on MPI and Kubernetes. It lets you run high‐performance fractal calculations across a cluster of pods.

---

## 📖 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Local Development](#local-development)
3. [Kubernetes Deployment](#kubernetes-deployment)
4. [Submitting MPI Jobs](#submitting-mpi-jobs)

---

## Architecture Overview

1. **Client** submits fractal parameters via REST to the **Server**.
2. **Server** enqueues a job in **Redis** (`RPUSH mpi_jobs ...`).
3. **Puller** watches Redis, then uses the Kubernetes API to:
   - Ensure the MPI StatefulSet (headless service + pods) is deployed
   - Wait for pods to become ready
   - Generate a hostfile and distribute SSH keys
   - Invoke `mpirun` on the master pod
4. The MPI C++ binary runs, writes out `fractal.png`, and exits.

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

# (optional) Monitor progress
watch kubectl get pods -n distributed-fractals

# To tear down
kubectl delete -k manifests/
minikube stop
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
- name: SLOTS_PER_NODE # slots per node for mpirun
```

### **Submitting MPI Jobs**

After Redis is running, push jobs like so:

```bash
kubectl exec -n distributed-fractals deploy/redis -- redis-cli
```

Inside the redis:

```bash
RPUSH mpi_jobs '{"args":[<args>]}'
```

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
