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

def watch_logs():
    w = watch.Watch()
    waiting_for_task = True

    last_percent = None
    percent_timestamp = None
    STUCK_TIMEOUT = 60  # seconds

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

            if waiting_for_task:
                if "[TASK]" in line:
                    waiting_for_task = False
                    last_percent = None
                    percent_timestamp = time.time()
                    print("[Observer] Detected start of new task")
                continue

            # En progreso de tarea
            if "[SUCCESS]" in line:
                update_job_status("success")
                waiting_for_task = True
                print("[Observer] Task succeeded, back to waiting for next task")
                continue

            if "[ERROR]" in line:
                update_job_status("fail")
                waiting_for_task = True
                print("[Observer] Task failed, back to waiting for next task")
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
                        waiting_for_task = True
                        print(f"[Observer] No progress for {STUCK_TIMEOUT}s, marking as failed")
                continue

    except ApiException as e:
        print(f"[Observer] K8s API error: {e}")
        update_job_status("fail")
    except Exception as e:
        print(f"[Observer] Unexpected error: {e}")
        update_job_status("fail")
    finally:
        w.stop()

if __name__ == "__main__":
    watch_logs()  
