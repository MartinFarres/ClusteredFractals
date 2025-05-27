## ──────── Stage 1: Build ────────
FROM debian:bookworm-slim AS builder
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    cmake \
    build-essential \
    openmpi-bin \
    libopenmpi-dev \
    libpng-dev \
    libz-dev && \
    rm -rf /var/lib/apt/lists/*

# Clone and build the project
WORKDIR /fractal
RUN git init && \
    git clone --depth 1 https://github.com/FrancoYudica/DistributedFractals.git
WORKDIR /fractal/DistributedFractals
RUN mkdir build && cd build && \
    cmake .. && make

## ──────── Stage 2: Runtime ────────
FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime-only dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openmpi-bin \
    libopenmpi3 \
    libpng16-16 \
    libz1 \
    sudo \
    openssh-server \
    sshpass \
    python3 \
    python3-pip \
    python3-redis && \
    rm -rf /var/lib/apt/lists/*

# Create mpi-user with sudo & ssh setup
RUN useradd -m -s /bin/bash mpi-user && \
    echo "mpi-user:mpi-password" | chpasswd && \
    echo "mpi-user ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/mpi-user && \
    chmod 0440 /etc/sudoers.d/mpi-user && \
    mkdir -p /home/mpi-user/.ssh && \
    chown -R mpi-user:mpi-user /home/mpi-user/.ssh

# Copy built project
COPY --from=builder /fractal /home/mpi-user/fractal
RUN chown -R mpi-user:mpi-user /home/mpi-user/fractal && \
    chmod -R a+x /home/mpi-user/fractal

# SSH setup
RUN mkdir /var/run/sshd
EXPOSE 22

# Copy entrypoint and socket handler
COPY entrypoint.sh /entrypoint.sh
COPY socket_handler.py /home/mpi-user/socket_handler.py
COPY run_and_check.py /home/mpi-user/run_and_check.py
RUN chmod +x /entrypoint.sh && \
    chown mpi-user:mpi-user /home/mpi-user/socket_handler.py /home/mpi-user/run_and_check.py

USER mpi-user
WORKDIR /home/mpi-user

ENTRYPOINT ["/entrypoint.sh"]
