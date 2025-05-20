FROM node:18-alpine
WORKDIR /app

# Copiamos package.json y package-lock.json (si lo generó npm)
COPY package*.json ./

# Instalamos dependencias
RUN npm install

# Copiamos el resto del código
COPY . .

# Exponemos el puerto en el que escucha Express
EXPOSE 30081

# Comando por defecto
CMD ["npm", "start"]
