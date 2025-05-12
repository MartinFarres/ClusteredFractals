# Usa una imagen base de Ubuntu
FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias necesarias
RUN apt-get update && \
    apt-get install -y \
    git \
    curl \
    pkg-config \
    openmpi-bin \
    libopenmpi-dev \
    libpng-dev \
    cmake \
    build-essential \
    libpng-dev \
    libz-dev \
    wget \
    g++ \
    openssh-server \
    nano \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario mpi-user con home y bash shell
RUN useradd -m -s /bin/bash mpi-user && \
    echo "mpi-user:mpi-password" | chpasswd && \
    mkdir -p /home/mpi-user/.ssh && \
    chown -R mpi-user:mpi-user /home/mpi-user/.ssh

#USER mpi-user

# Crear la carpeta fractal
RUN mkdir -p /fractal

# Cambiar al directorio fractal
WORKDIR /fractal

# Inicializar git y clonar el repositorio
RUN git init && \
    git clone https://github.com/FrancoYudica/DistributedFractals.git

# Cambiar al directorio del repositorio clonado
WORKDIR /fractal/DistributedFractals

# Crear el directorio build y compilar el proyecto
RUN mkdir build && \
    cd build && \
    cmake .. && \
    make

RUN chmod -R 777 /fractal

#USER root

# Configurar el servicio SSH
RUN mkdir /var/run/sshd

# Exponer el puerto 22
EXPOSE 22

COPY entrypoint.sh /entrypoint.sh
RUN chmod a+x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
