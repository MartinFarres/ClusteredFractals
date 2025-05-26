# Usa una imagen base de Ubuntu LTS
FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/home/mpi-user

# 1. Instala dependencias de sistema y Python en una sola capa
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        curl \
        git \
        libopenmpi-dev \
        openmpi-bin \
        libpng-dev \
        libz-dev \
        openssh-server \
        sshpass \
        sudo \
        wget \
        python3 \
        python3-pip \
        nano \
    && rm -rf /var/lib/apt/lists/* \
    # 2. Crea usuario mpi-user y configura sudo/SSH
    && useradd -m -s /bin/bash mpi-user \
    && echo 'mpi-user:mpi-password' | chpasswd \
    && mkdir -p $HOME/.ssh \
    && chown -R mpi-user:mpi-user $HOME/.ssh \
    && echo 'mpi-user ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# 3. Configura SSH
RUN mkdir /var/run/sshd

# 4. Prepara el workspace y clona el proyecto
USER mpi-user
WORKDIR /fractal
RUN git clone https://github.com/FrancoYudica/DistributedFractals.git .

# 5. Instala dependencias Python y Redis client
RUN pip3 install --no-cache-dir redis

# 6. Compila el proyecto
RUN mkdir build && cd build && \
    cmake .. && make

# 7. Copia scripts de entrada y handler
COPY --chown=mpi-user:mpi-user entrypoint.sh /entrypoint.sh
COPY --chown=mpi-user:mpi-user socket_handler.py $HOME/socket_handler.py
RUN chmod +x /entrypoint.sh

# 8. Exponer SSH si lo necesitas
EXPOSE 22

ENTRYPOINT ["/entrypoint.sh"]
