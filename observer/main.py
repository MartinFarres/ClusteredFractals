import os
import redis
import time
import json
from kubernetes import client, config, watch

# --- Setup ---
config.load_incluster_config()
v1 = client.CoreV1Api()
redis_host = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(host=redis_host, port=6379, db=0)
NAMESPACE = os.getenv("POD_NAMESPACE", "default")
MASTER_POD = os.getenv("MASTER_POD", "mpi-node-0")

# --- Update Redis status ---
def update_job_status(new_status):
    tasks = r.lrange("running_tasks", 0, -1)
    for task in tasks:
        data = json.loads(task)
        if data.get("name_space") == NAMESPACE:
            data["status"] = new_status
            r.lrem("running_tasks", 0, task)
            r.lpush("running_tasks", json.dumps(data))
            print(f"Updated status to '{new_status}' for job in namespace '{NAMESPACE}'")
            return

# --- Watch master logs ---
def watch_logs():
    print("Watching logs from master...")
    last_percent = None
    same_percent_time = None

    w = watch.Watch()
    try:
        # lee logs en tiempo real
        for line in w.stream(v1.read_namespaced_pod_log, name=MASTER_POD, namespace=NAMESPACE, follow=True, _preload_content=True):
            line = line.strip()
            print("Log:", line)

            if "[SUCCESS]" in line:
                update_job_status("success")
                break
            elif "[ERROR]" in line:
                update_job_status("fail")
                break
            # caso de un mensaje como "Progress: 84.3%"
            elif "[STATUS]" in line and "%" in line:
                try:
                    # Toma el porcentaje y si no cambió por más de 60 segs lo toma como fail"
                    percent = float(line.split("%")[0].split()[-1])
                    if percent == last_percent:
                        if same_percent_time and time.time() - same_percent_time > 60:  # 1 min stuck
                            update_job_status("fail")
                            break
                    else:
                        last_percent = percent
                        same_percent_time = time.time()
                except ValueError:
                    continue
    except Exception as e:
        print("Error watching logs:", e)
        update_job_status("fail")


if __name__ == "__main__":
    while True:
        try:
            watch_logs()
        except Exception as e:
            print(f"watch_logs raised an exception: {e}")
        # Espera breve antes de volver a iniciar el watch
        time.sleep(5)

