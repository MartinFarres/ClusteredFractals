#!/bin/bash

# Start SSH daemon as root
sudo /usr/sbin/sshd

# Generate SSH key for mpi-user if it doesn't exist
if [ ! -f "/home/mpi-user/.ssh/id_rsa" ]; then
  ssh-keygen -t rsa -b 4096 -f /home/mpi-user/.ssh/id_rsa -N ''
fi

# Keep container running
exec tail -f /dev/null
