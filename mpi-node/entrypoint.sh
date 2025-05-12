#!/bin/bash

/usr/sbin/sshd

# Generate SSH key if it doesn't exist
if [ ! -f "/home/mpi-user/.ssh/id_rsa" ]; then
  ssh-keygen -t rsa -b 4096 -f /home/mpi-user/.ssh/id_rsa -N ""
fi

exec su - mpi-user

# Execute any command passed to the container or open a shell
tail -f /dev/null
exec "$@"
