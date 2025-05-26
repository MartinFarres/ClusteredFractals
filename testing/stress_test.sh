#!/bin/bash

# Número total de peticiones
TOTAL_REQUESTS=29

# Concurrencias simultáneas
CONCURRENCY=1

# Endpoint y payload
URL="http://192.168.59.100:30080/api/submit-job"
PAYLOAD='{"width":"600","height":600,"block_size":"64","samples":1,"camerax":0,"cameray":0,"zoom":1.2,"type":1,"color_mode":2}'

# Ejecutar peticiones en paralelo usando bash -c directamente
seq $TOTAL_REQUESTS | xargs -n1 -P$CONCURRENCY -I{} bash -c "
  curl -s -o /dev/null -w '%{http_code}\n' --location --request PUT \"$URL\" \
  --header 'Content-Type: application/json' \
  --data '$PAYLOAD'
"
