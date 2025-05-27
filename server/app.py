from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import redis
import uuid
import json

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
        params = ['width','height','block_size','samples','camerax','cameray','zoom','type', 'color_mode']
        for p in params:
            _ = body[p]
        width, height, block_size = map(int, [body['width'], body['height'], body['block_size']])
        samples = int(body['samples'])
        camera_x, camera_y, zoom = map(float, [body['camerax'], body['cameray'], body['zoom']])
        render_type = int(body['type'])
        color_mode = int(body['color_mode'])
    except Exception:
        return jsonify({"error": "Parámetros inválidos"}), 400

    # Store uuid in images hash map
    r.hset('completed_tasks', job_uuid, b'')

    # Queue job
    job_data = {
        'uuid': job_uuid,
        'width': width,
        'height': height,
        'block_size': block_size,
        'samples': samples,
        'camera_x': camera_x,
        'camera_y': camera_y,
        'zoom': zoom,
        'type': render_type,
        'color_mode': color_mode,
    }
    r.lpush('pending_tasks', json.dumps(job_data))
    app.logger.info(f"Queued job: {job_data}")
    return jsonify({"uuid": job_uuid}), 202

@app.route('/api/get-image/<uuid>', methods=['GET'])
def get_image(uuid):
    try:
        image = r.hget('completed_tasks', uuid)
        if image is None:
            return jsonify({'error':'UUID not found'}), 404
        if image == b'':
            return jsonify({'message':'Still processing'}), 202

        r.hdel('completed_tasks', uuid)
        return Response(image, mimetype='image/png'), 200

    except redis.RedisError as e:
        app.logger.error(f"Redis error: {e}")
        return jsonify({'error':'Redis error','details':str(e)}), 500

    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
        return jsonify({'error':'Unexpected error','details':str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
