import os
import redis
import time
import json
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

# --- Setup ---
config.load_incluster_config()
v1 = client.CoreV1Api()

redis_host = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(host=redis_host, port=6379, db=0)

NAMESPACE  = os.getenv("POD_NAMESPACE", "default")
MASTER_POD = os.getenv("MASTER_POD", "mpi-node-0")

def update_job_status(new_status):
    tasks = r.lrange("running_tasks", 0, -1)
    for task in tasks:
        data = json.loads(task)
        if data.get("namespace") == NAMESPACE:
            data["status"] = new_status
            r.lrem("running_tasks", 0, task)
            r.lpush("running_tasks", json.dumps(data))
            print(f"[Observer] Updated status to '{new_status}' for namespace '{NAMESPACE}'")
            break

def pod_is_running():
    try:
        pod = v1.read_namespaced_pod(name=MASTER_POD, namespace=NAMESPACE)
        return pod.status.phase == "Running"
    except ApiException as e:
        if e.status == 404:
            print("[Observer] Master pod not found (was probably deleted).")
        else:
            print(f"[Observer] Failed to get pod status: {e}")
        return False

def watch_logs():
    STUCK_TIMEOUT = 60  # seconds without progress
    RETRY_DELAY = 5     # seconds between retries

    while True:
        if not pod_is_running():
            print("[Observer] Master pod is not running. Marking task as failed.")
            update_job_status("fail")
            return

        w = watch.Watch()
        task_in_progress = False
        last_percent = None
        percent_timestamp = None

        print("[Observer] Starting log watch (stream open)...")

        try:
            for line in w.stream(
                v1.read_namespaced_pod_log,
                name=MASTER_POD,
                namespace=NAMESPACE,
                follow=True,
                _preload_content=True
            ):
                line = line.strip()
                if not line:
                    continue

                print(f"[Master Log] {line}")

                if "[TASK]" in line:
                    task_in_progress = True
                    last_percent = None
                    percent_timestamp = time.time()
                    print("[Observer] Detected start of new task")
                    continue

                if "[SUCCESS]" in line:
                    update_job_status("success")
                    task_in_progress = False
                    print("[Observer] Task succeeded")
                    continue

                if "[ERROR]" in line:
                    update_job_status("fail")
                    task_in_progress = False
                    print("[Observer] Task failed")
                    continue

                if "[STATUS]" in line and "%" in line:
                    try:
                        percent = float(line.split("%")[0].split()[-1])
                    except ValueError:
                        continue

                    now = time.time()
                    if last_percent is None or percent != last_percent:
                        last_percent = percent
                        percent_timestamp = now
                        print(f"[Observer] Progress: {percent}%")
                    else:
                        if now - percent_timestamp > STUCK_TIMEOUT:
                            update_job_status("fail")
                            task_in_progress = False
                            print(f"[Observer] No progress for {STUCK_TIMEOUT}s, marking as failed")
                    continue

        except ApiException as e:
            print(f"[Observer] K8s API error: {e}")
            if e.status in [404, 410, 500]:
                print("[Observer] Lost connection with master pod or pod deleted.")
                if task_in_progress:
                    print("[Observer] Task was in progress. Marking as failed.")
                    update_job_status("fail")
                return

        except Exception as e:
            print(f"[Observer] Unexpected error: {e}")
            if task_in_progress:
                update_job_status("fail")
                print("[Observer] Task was in progress. Marking as failed due to unexpected error.")
            return

        finally:
            w.stop()
            if not pod_is_running():
                print("[Observer] Pod not running during final check.")
                if task_in_progress:
                    update_job_status("fail")
                    print("[Observer] Task was in progress. Marking as failed.")
                return

            if task_in_progress:
                print("[Observer] Log stream ended during task. Marking task as failed.")
                update_job_status("fail")
                return  # No retry

            print(f"[Observer] Log stream ended. Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

if __name__ == "__main__":
    watch_logs()  
