#!/bin/bash
MAX_RETRIES=5

# Check if command arguments are provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <command> [args...]"
    exit 1
fi

# Retry loop
n=$MAX_RETRIES
while ((n--)); do
    $@ && break || {
        echo "Failed to run command $((MAX_RETRIES-n))/$MAX_RETRIES times"
        if ((n == 0)); then
            echo "Exiting retry!!!"
            exit $?
        fi
    }
done
