from flask import Flask, request, send_file
from flask_cors import CORS
import os
import subprocess
import time

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'generated')

os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.route('/render', methods=['POST'])
def render_image():
    # Obtener parámetros
    width = int(request.get_json().get('width'))
    height = int(request.get_json().get('height'))
    block_size = int(request.get_json().get('block_size'))
    samples = int(request.get_json().get('samples'))
    camera_x = float(request.get_json().get('camerax'))
    camera_y = float(request.get_json().get('cameray'))
    zoom = float(request.get_json().get('zoom'))
    render_type = int(request.get_json().get('type'))

    # Nombre de archivo de salida único
    filename = f"img_{time.time_ns()}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)

    # Ejecutar el programa externo (sin bloquear completamente Flask)
    try:
        subprocess.run([
            "mpirun", "-np", "4", "./server/fractal_mpi",
            "-w", str(width), "--height", str(height),
            "-s", str(samples), "-b", str(block_size),
            "-z", str(zoom), "-cx", str(camera_x), "-cy", str(camera_y),
            "-t", str(render_type),
            "-o", filepath
        ], check=True)
        
    except subprocess.CalledProcessError:
        return {"error": "Error al generar la imagen"}, 500

    # Enviar imagen generada
    if not os.path.exists(filepath):
        return {"error": "Imagen no encontrada"}, 404

    return send_file(filepath, mimetype='image/png')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
