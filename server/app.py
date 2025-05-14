from flask import Flask, request, jsonify, Response
import redis
import socket
import threading

# Initialize the Flask application
app = Flask(__name__)

# Set up Redis (if needed for job data storage)
r = redis.Redis(host='redis.default.svc.cluster.local', port=6379, db=0)

done = False

# Route to receive the job parameters (for image generation)
@app.route('/api/submit-job', methods=['PUT'])
def submit_job():
    try:
        # Retrieve the parameters from the request
        width = int(request.get_json().get('width'))
        height = int(request.get_json().get('height'))
        block_size = int(request.get_json().get('block_size'))
        samples = int(request.get_json().get('samples'))
        camera_x = float(request.get_json().get('camerax'))
        camera_y = float(request.get_json().get('cameray'))
        zoom = float(request.get_json().get('zoom'))
        render_type = int(request.get_json().get('type'))

        # Form the job data
        job_data = {
            'width': width,
            'height': height,
            'block_size': block_size,
            'samples': samples,
            'camerax': camera_x,
            'cameray': camera_y,
            'zoom': zoom,
            'type': render_type
        }

        # Push the job to Redis (jobs queue)
        r.lpush("mpi_jobs", str(job_data))  # Convert the dict to a string for storage in Redis
        print(f"Job parameters received: {job_data}")
        
        return jsonify({"status": "Job submitted successfully"}), 200

    except Exception as e:
        print(f"Error in receiving job: {e}")
        return jsonify({"error": "Failed to process job"}), 400

# Route to receive the image buffer from the master node and send it to the client
@app.route('/api/upload-image', methods=['PUT'])
def upload_image():
    try:
        # Get the image data from the request (buffer)
        img_data = request.data

        # Send the image buffer directly to the client as a response
        return Response(img_data, mimetype='image/png')

    except Exception as e:
        print(f"Error in uploading image: {e}")
        return jsonify({"error": "Failed to upload image"}), 400

# Simple TCP server that accepts connections and expects 
# a PNG formatted buffer image. 
def run_server():
    HOST = 5001
    PORT = '0.0.0.0'
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
            data = b''
            expected_size = int.from_bytes(client_socket.recv(4), byteorder='big')

            while len(data) < expected_size:
                packet = client_socket.recv(4096)
                if not packet:
                    break
                data += packet

            #image_generated_callback(data)
            with open("imagen_recibida.png", "wb") as f:
                f.write(data) 
        finally:
            client_socket.close()

    server_socket.close()

if __name__ == '__main__':
    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    # Run the server on the specified port
    app.run(host='0.0.0.0', port=5000)
