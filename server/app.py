from flask import Flask, request, jsonify, Response
import redis
import socket
import threading
import uuid
import json
import requests 

# Initialize the Flask application
app = Flask(__name__)

# Set up Redis
r = redis.Redis(host='redis.default.svc.cluster.local', port=6379, db=0)


# Route to submit the job
@app.route('/api/submit-job', methods=['PUT'])
def submit_job():
    body = request.get_json(force=True)
    # Generates UUID
    job_uuid = str(uuid.uuid4())

    # Gets Params
    try:
        width      = int(body['width'])
        height     = int(body['height'])
        block_size = int(body['block_size'])
        samples    = int(body['samples'])
        camera_x   = float(body['camerax'])
        camera_y   = float(body['cameray'])
        zoom       = float(body['zoom'])
        render_type= int(body['type'])
    except (KeyError, ValueError):
        return jsonify({"error": "Parámetros inválidos"}), 400

    # Gets callback url
    callback_url = body.get('callback_url')
    if not callback_url:
        return jsonify({"error": "callback_url es obligatorio"}), 400

    # Save UUID: callback_url in Redis
    r.hset('callbacks', job_uuid, callback_url)

    # Push Job to Redis (with UUID)
    job_data = {
        'uuid': job_uuid,
        'width': width,
        'height': height,
        'block_size': block_size,
        'samples': samples,
        'camerax': camera_x,
        'cameray': camera_y,
        'zoom': zoom,
        'type': render_type
    }
    r.lpush("mpi_jobs", json.dumps(job_data))

    # Return msg to client
    return jsonify({"uuid": job_uuid}), 202


def run_socket_listener():
    """
    Thread that listenst to the socket in 5001
    A Waits:
      1) UUID size
      2) UUID
      3) Image size
      4) Buffer PNG
    """
    HOST = '0.0.0.0'
    PORT = 5001
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"[Socket] escuchando en {HOST}:{PORT}")

    while True:
        client_sock, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(client_sock,)).start()


def handle_client(client_sock):
    try:
        # Gets UUID Size
        raw = client_sock.recv(4)
        if len(raw) < 4:
            return
        uuid_len = int.from_bytes(raw, byteorder='big')

        # Gets UUID
        uuid_bytes = b''
        while len(uuid_bytes) < uuid_len:
            chunk = client_sock.recv(uuid_len - len(uuid_bytes))
            if not chunk:
                return
            uuid_bytes += chunk
        job_uuid = uuid_bytes.decode('utf-8')

        # Gets image buffer size
        raw = client_sock.recv(4)
        if len(raw) < 4:
            return
        img_len = int.from_bytes(raw, byteorder='big')

        # Gets buffer image
        img_data = b''
        while len(img_data) < img_len:
            packet = client_sock.recv(min(4096, img_len - len(img_data)))
            if not packet:
                break
            img_data += packet

        # Gets back callback_url from redis using uuid
        entry = r.hget('callbacks', job_uuid)
        if not entry:
            print(f"[Socket] UUID desconocido o ya procesado: {job_uuid}")
            return
        callback_url = entry.decode('utf-8')

        # POST image to corresponding client
        try:
            headers = {'Content-Type': 'image/png', 'X-Job-UUID': job_uuid}
            resp = requests.post(callback_url, data=img_data, headers=headers, timeout=5)
            if resp.status_code // 100 != 2:
                print(f"[Socket] Error {resp.status_code} reenviando a {callback_url}")
        except requests.RequestException as e:
            print(f"[Socket] Falló POST a {callback_url}: {e}")

        # Cleans Redis
        r.hdel('callbacks', job_uuid)

    finally:
        client_sock.close()


if __name__ == '__main__':
    # Start thread listening in background socket
    t = threading.Thread(target=run_socket_listener, daemon=True)
    t.start()
    # Start Flask in port 5000
    app.run(host='0.0.0.0', port=5000)
