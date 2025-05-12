# Variables
CLIENT_DIR=client
SERVER_DIR=server
VENV_DIR=$(SERVER_DIR)/.venv

# Comandos
.PHONY: all install run-client run-server dev clean

# Instala dependencias del servidor y cliente
install:
	python3 -m venv $(VENV_DIR)
	. $(VENV_DIR)/bin/activate && pip install -r $(SERVER_DIR)/requirements.txt
	cd $(CLIENT_DIR) && npm install

# Levanta solo el servidor Flask
run-server:
	. $(VENV_DIR)/bin/activate && python $(SERVER_DIR)/app.py

# Levanta solo el cliente React
run-client:
	cd $(CLIENT_DIR) && npm start

# Levanta ambos en paralelo
dev:
	make -j2 run-server run-client

# Limpia entorno virtual y dependencias del cliente
clean:
	rm -rf $(VENV_DIR)
	cd $(CLIENT_DIR) && rm -rf node_modules
