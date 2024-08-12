#!/bin/bash

# Define temporary file for logging
LOGFILE="./cartesi_node.log"

# function to print successful messages
print_success() {
    local input_string="$1"
    local check_icon="✓"
    printf "\e[32m$check_icon $input_string\e[0m\n"
}

# function to print the start of a section / operation
print_section() {
    local input_string="$1"
    local prefix_icon="➤"  # You can change the icon as needed
    printf "$prefix_icon $input_string\n"
}

# Function to stop and clean up processes and containers
cleanup() {
    print_section "Cleaning up..."

    # Stop and remove Docker containers matching the pattern "cartesi-node-*"
    echo "Stopping and removing Docker containers..."
    docker stop $(docker ps -q -f name=cartesi-node-*)
    docker rm $(docker ps -aq -f name=cartesi-node-*)

    # Kill all background jobs if any are running
    echo "Stopping all background jobs..."
    kill $(jobs -p)
    wait $(jobs -p) 2>/dev/null

    print_success "Cleanup complete."
    exit 0
}

# Trap SIGINT and SIGTERM signals and call cleanup function
trap cleanup SIGINT SIGTERM

# Stop and remove Docker containers matching the pattern "cartesi-node-*"
print_section "Checking for existing Cartesi node containers..."
CONTAINERS=$(docker ps -q -f name=cartesi-node-*)
if [ ! -z "$CONTAINERS" ]; then
    echo "Stopping and removing existing Cartesi node containers..."
    docker stop $CONTAINERS
    docker rm $CONTAINERS
fi

# Start the Cartesi node in development mode and redirect output to a logfile
print_section "Starting Cartesi node in development mode..."
cartesi run --no-backend --verbose --epoch-duration=1 > $LOGFILE 2>&1 &

# Get the process ID of the Cartesi node
NODE_PID=$!

# Function to check log file for a specific message
check_log() {
    grep -q "Press Ctrl+C to stop the node" $LOGFILE
    return $?
}

# Wait for the specific log message to appear
print_section "Waiting for the node to be ready..."
while ! check_log; do
    sleep 1
done

print_success "Cartesi node is ready."

print_section "Starting dapp process..."
(   
    cd cartesi-dapp
    source venv/bin/activate
    python sqlite.py && ROLLUP_HTTP_SERVER_URL="http://127.0.0.1:8080/host-runner" python3 -m dapp.dapp > /dev/null 2>&1
) &

print_section "Starting the test script"
(   
    forge build
    cd scripts
    yarn generate-contract-types
    yarn start 2>&1 | sed 's/^/[DEMO] /'
) &

# Wait for the Cartesi node process to finish
wait $NODE_PID

print_success "All processes have been terminated."