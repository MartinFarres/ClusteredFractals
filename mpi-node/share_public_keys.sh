#!/bin/bash
# Script that shares the public key of this computer to all the listed nodes of the cluster
# The list should be provided as an argument

# Check if the correct number of arguments are provided
if [ "$#" -ne 1 ]; then
    echo "Usage: nodes_username_ip_list.txt"
    exit 1
fi

# Set the file that contains the list of IPs (passed as the first parameter)
IP_FILE="$1"

# Check if the IP list file exists
if [ ! -f "$IP_FILE" ]; then
    echo "The file $IP_FILE does not exist."
    exit 1
fi

# Loop through each line in the IP list file
while IFS=' ' read -r username ip || [ -n "$username" ]; do
    # Skip empty lines
    if [ -z "$username" ] || [ -z "$ip" ]; then
        continue
    fi

    echo "Sharing public key to $username@$ip"
    
    ssh-copy-id "$username@$ip"

    # Check if the ssh-copy-id command was successful
    if [ "$?" -ne 0 ]; then
        echo "Error copying to $username@$ip"
    else
        echo "Successfully copied to $username@$ip"
    fi
done < "$IP_FILE"