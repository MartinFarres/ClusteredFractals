from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import redis
import socket
import threading
import uuid
import json
import requests

# Initialize Flask
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Redis client
r = redis.Redis(host='redis', port=6379, db=0)

done = False

@app.route('/api/submit-job', methods=['PUT'])
def submit_job():
    body = request.get_json(force=True)
    job_uuid = str(uuid.uuid4())

    try:
        # Validate parameters
        params = ['width','height','block_size','samples','camerax','cameray','zoom','type']
        for p in params:
            _ = body[p]
        width, height, block_size = map(int, [body['width'], body['height'], body['block_size']])
        samples = int(body['samples'])
        camera_x, camera_y, zoom = map(float, [body['camerax'], body['cameray'], body['zoom']])
        render_type = int(body['type'])
    except Exception:
        return jsonify({"error": "Parámetros inválidos"}), 400

    callback_url = body.get('callback_url')
    if not callback_url:
        return jsonify({"error": "callback_url es obligatorio"}), 400

    # Store callback
    r.hset('callbacks', job_uuid, callback_url)

    # Queue job
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
    r.lpush('mpi_jobs', json.dumps(job_data))
    app.logger.info(f"Queued job: {job_data}")
    return jsonify({"uuid": job_uuid}), 202

def run_server():
    HOST = '0.0.0.0'
    PORT = 5001
    global done
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    server_socket.settimeout(1.0)  # Set timeout for accept()

    print(f"Server is listening on port {PORT}")
    while not done:
        try:
            client_socket, _ = server_socket.accept()
        except socket.timeout:
            continue  # Just try again in the next loop iteration

        # Handle the client
        try:
            # Step 1: Receive UUID length (4 bytes depending on sender)
            uuid_len_bytes = recv_exact(client_socket, 4)
            uuid_len = int.from_bytes(uuid_len_bytes, byteorder='big')

            # Step 2: Receive UUID string
            uuid_bytes = recv_exact(client_socket, uuid_len)
            uuid = uuid_bytes.decode('utf-8')
            print(f"UUID: {uuid}")

            # Step 3: Receive buffer size (4 bytes for uint32)
            buf_size_bytes = recv_exact(client_socket, 4)
            buf_size = int.from_bytes(buf_size_bytes, byteorder='big')
            print(buf_size)

            # Step 4: Receive the buffer (image or binary data)
            img_data = recv_exact(client_socket, buf_size)

            # Procesamiento y reenvío...
            entry = r.hget('callbacks', uuid)
            if not entry:
                app.logger.warning(f"Unknown UUID: {uuid}")
                return
            callback_url = entry.decode('utf-8')
            headers = {'Content-Type': 'image/png', 'X-Job-UUID': uuid}
            try:
                resp = requests.post(callback_url, data=img_data, headers=headers, timeout=5)
                if not resp.ok:
                    app.logger.error(f"Error {resp.status_code} forwarding to {callback_url}")
            except Exception as e:
                app.logger.error(f"Exception posting to callback: {e}")
            finally:
                r.hdel('callbacks', uuid)
        finally:
            client_socket.close()

    server_socket.close()

def recv_exact(sock, num_bytes):
    """Receive exactly num_bytes from the socket."""
    data = b''
    while len(data) < num_bytes:
        packet = sock.recv(num_bytes - len(data))
        if not packet:
            raise ConnectionError("Client disconnected")
        data += packet
    return data

if __name__ == '__main__':
    threading.Thread(target=run_server, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
