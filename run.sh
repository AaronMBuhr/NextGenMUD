#!/bin/bash

# Parse command line arguments
UVICORN_ARGS=()
APP_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --log-width)
            LOG_WIDTH="$2"
            # Only export if a valid width is specified
            if [[ "$LOG_WIDTH" =~ ^[0-9]+$ ]]; then
                export NEXTGENMUD_LOG_WIDTH=$LOG_WIDTH
            fi
            shift 2
            ;;
        *)
            # Pass all other arguments to uvicorn
            UVICORN_ARGS+=("$1")
            shift
            ;;
    esac
done

# Start the application with uvicorn
uvicorn NextGenMUD.asgi:application --host 0.0.0.0 --port 8000 "${UVICORN_ARGS[@]}"
