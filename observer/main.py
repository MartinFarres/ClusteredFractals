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

NAMESPACE  = os.getenv("POD_NAMESPACE")
MASTER_POD = os.getenv("MASTER_POD")

# --- Update Redis status ---
def update_job_status(new_status):
    tasks = r.lrange("running_tasks", 0, -1)
    for task in tasks:
        data = json.loads(task)
        if data.get("namespace") == NAMESPACE:
            data["status"] = new_status
            r.lrem("running_tasks", 0, task)
            r.lpush("running_tasks", json.dumps(data))
            print(f"[Observer] Updated status to '{new_status}' for job in namespace '{NAMESPACE}'")
            break

# --- Watch master logs indefinitely ---
def watch_logs():
    w = watch.Watch()
    waiting_for_task = True

    # Para STATUS
    last_percent = None
    percent_timestamp = None
    STUCK_TIMEOUT = 60  # segundos

    print("[Observer] Starting log watch...")
    try:
        for raw in w.stream(
            v1.read_namespaced_pod_log,
            name=MASTER_POD,
            namespace=NAMESPACE,
            follow=True,
            _preload_content=True,    # <-- línea completa
            tail_lines=1   
        ):
            line = raw.decode('utf-8', errors='ignore').strip()
            print(f"[Master Log] {line}")

            # 1) Buscamos el inicio de la tarea
            if waiting_for_task:
                if "[Task]" in line:
                    waiting_for_task = False
                    last_percent = None
                    percent_timestamp = time.time()
                    print("[Observer] Detected start of new task")
                continue  # seguimos leyendo

            # 2) Una vez que la tarea arrancó...

            # 2a) Éxito o fallo explícito
            if "[SUCCESS]" in line:
                update_job_status("success")
                waiting_for_task = True
                print("[Observer] Task succeeded, returning to waiting state")
                break

            if "[ERROR]" in line:
                update_job_status("fail")
                waiting_for_task = True
                print("[Observer] Task failed, returning to waiting state")
                break

            # 2b) Progreso intermedio
            if "[STATUS]" in line and "%" in line:
                try:
                    # extraer el número antes de '%'
                    percent = float(line.split("%")[0].split()[-1])
                except ValueError:
                    continue

                now = time.time()
                if last_percent is None or percent != last_percent:
                    # primer dato o cambio de porcentaje
                    last_percent = percent
                    percent_timestamp = now
                    print(f"[Observer] Progress updated to {percent}%")
                else:
                    # porcentaje igual al anterior
                    if now - percent_timestamp > STUCK_TIMEOUT:
                        update_job_status("fail")
                        waiting_for_task = True
                        print(f"[Observer] No progress for {STUCK_TIMEOUT}s, marking task as failed")
                        break
                continue

            # otros logs se ignoran...

    except ApiException as e:
        print(f"[Observer] K8s API error: {e}")
        update_job_status("fail")
    except Exception as e:
        print(f"[Observer] Unexpected error: {e}")
        update_job_status("fail")
    finally:
        w.stop()

if __name__ == "__main__":
    while True:
        watch_logs()
        # brevemente esperamos antes de reconectar
        time.sleep(2)
