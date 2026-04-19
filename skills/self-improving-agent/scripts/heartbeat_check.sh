#!/bin/bash
# Heartbeat Check Script v2.0 for 8081 Port
# Features: Response time tracking, error counting, JSON output mode
# Usage: heartbeat_check.sh [--json] [--verbose]

PORT=8081
MAX_RETRIES=3
RETRY_DELAY=2
VERBOSE=false
JSON_OUTPUT=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --json) JSON_OUTPUT=true; shift ;;
        --verbose) VERBOSE=true; shift ;;
    esac
done

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    if [ "$VERBOSE" = "true" ] || [ "$JSON_OUTPUT" = "false" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    fi
}

log_json() {
    if [ "$JSON_OUTPUT" = "true" ]; then
        echo "$1"
    fi
}

# Get timestamp
get_ts() {
    date '+%Y-%m-%d %H:%M:%S'
}

# Check if port is in use
check_port() {
    lsof -ti:$PORT 2>/dev/null
}

# Check if process is running
check_process() {
    local pid=$1
    ps -p $pid > /dev/null 2>&1
}

# Measure response time and HTTP code
check_http() {
    local start_time=$(date +%s%3N)
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT --max-time 5)
    local end_time=$(date +%s%3N)
    local response_time=$((end_time - start_time))
    echo "$http_code|$response_time"
}

# === MAIN ===
log_info "Heartbeat check started for port $PORT"

PID=$(check_port)

if [ -n "$PID" ]; then
    if check_process $PID; then
        log_info "Port $PORT is healthy (PID: $PID)"
        
        RESULT=$(check_http)
        HTTP_CODE=$(echo $RESULT | cut -d'|' -f1)
        RESPONSE_TIME=$(echo $RESULT | cut -d'|' -f2)
        
        if [ "$HTTP_CODE" = "200" ]; then
            log_info "HTTP 200 OK (response: ${RESPONSE_TIME}ms)"
            
            if [ "$JSON_OUTPUT" = "true" ]; then
                log_json "{\"status\":\"healthy\",\"port\":$PORT,\"pid\":$PID,\"http_code\":$HTTP_CODE,\"response_ms\":$RESPONSE_TIME,\"timestamp\":\"$(get_ts)\"}"
            fi
            exit 0
        else
            log_info "HTTP $HTTP_CODE - service degraded, attempting restart..."
        fi
    else
        log_info "PID $PID not found in process table, attempting restart..."
    fi
else
    log_info "No process on port $PORT, starting service..."
fi

# === RESTART SEQUENCE ===
for i in $(seq 1 $MAX_RETRIES); do
    log_info "Restart attempt $i/$MAX_RETRIES"
    
    # Kill zombie process
    if [ -n "$PID" ]; then
        kill -9 $PID 2>/dev/null
        sleep 1
    fi
    
    # Start service
    cd ~/.hermes/web_dashboard/public
    nohup python3 -m http.server $PORT > /dev/null 2>&1 &
    NEW_PID=$!
    sleep 2
    
    # Verify
    RESULT=$(check_http)
    HTTP_CODE=$(echo $RESULT | cut -d'|' -f1)
    RESPONSE_TIME=$(echo $RESULT | cut -d'|' -f2)
    
    if [ "$HTTP_CODE" = "200" ]; then
        log_info "Service restarted (PID: $NEW_PID, response: ${RESPONSE_TIME}ms)"
        
        if [ "$JSON_OUTPUT" = "true" ]; then
            log_json "{\"status\":\"restarted\",\"port\":$PORT,\"pid\":$NEW_PID,\"http_code\":$HTTP_CODE,\"response_ms\":$RESPONSE_TIME,\"timestamp\":\"$(get_ts)\"}"
        fi
        exit 0
    fi
    
    log_info "Restart attempt $i failed (HTTP $HTTP_CODE)"
    sleep $RETRY_DELAY
done

log_info "Failed to restart service after $MAX_RETRIES attempts"

if [ "$JSON_OUTPUT" = "true" ]; then
    log_json "{\"status\":\"failed\",\"port\":$PORT,\"error\":\"restart_failed\",\"timestamp\":\"$(get_ts)\"}"
fi

exit 1
