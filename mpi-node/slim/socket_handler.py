import redis
import socket
import threading


# Redis client
r = redis.Redis(host='redis.distributed-fractals', port=6379, db=0)

done = False

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
            job_uuid = uuid_bytes.decode('utf-8')
            print(f"UUID: {job_uuid}")

            # Step 3: Receive buffer size (4 bytes for uint32)
            buf_size_bytes = recv_exact(client_socket, 4)
            buf_size = int.from_bytes(buf_size_bytes, byteorder='big')
            print(buf_size)

            # Step 4: Receive the buffer (image or binary data)
            img_data = recv_exact(client_socket, buf_size)

            # Step 5: Updates redis with image
            r.hset('images', job_uuid, img_data)

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