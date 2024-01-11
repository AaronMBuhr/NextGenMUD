#!/bin/bash

# Default port number
DEFAULT_PORT=8000

# Check if a port number is provided as an argument
if [ "$1" != "" ]; then
    PORT=$1
else
    PORT=$DEFAULT_PORT
fi

# Start Daphne server
echo "Starting Daphne on port $PORT..."
daphne -p $PORT NextGenMUD.asgi:application
