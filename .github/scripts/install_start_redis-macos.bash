#!/usr/bin/env bash
set -euo pipefail

echo "Installing redis via Homebrew"
if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew not found in PATH; cannot install redis." >&2
    exit 2
fi

# Install redis if not already installed
if ! brew list redis >/dev/null 2>&1; then
    brew update || true
    brew install redis
else
    echo "redis already installed via Homebrew"
fi

# Start via brew services (will work on hosted macOS runners)
brew services start redis || true

# locate redis-cli and redis log
REDIS_CLI="$(command -v redis-cli || true)"
BREW_PREFIX="$(brew --prefix)"
REDIS_LOG="${BREW_PREFIX}/var/log/redis.log"

echo "redis-cli: ${REDIS_CLI:-not found}, redis log: ${REDIS_LOG}"

echo "Waiting for redis to become available (up to ~30s)"
UP=false
for i in {1..30}; do
    sleep 1
    echo "check attempt $i"
    if [ -n "${REDIS_CLI}" ]; then
        if ${REDIS_CLI} ping >/dev/null 2>&1; then
            echo "redis is up"
            UP=true
            break
        fi
    else
        # fall back to a TCP check using nc if available
        if command -v nc >/dev/null 2>&1; then
            if nc -z 127.0.0.1 6379 >/dev/null 2>&1; then
                echo "redis port is open (nc)"
                UP=true
                break
            fi
        fi
    fi
done

if [ "$UP" != true ]; then
    echo "=== redis did not become reachable within timeout ===" >&2
    if [ -f "$REDIS_LOG" ]; then
        echo "--- redis log (tail) ---"
        tail -n 200 "$REDIS_LOG" || true
    else
        echo "redis log not found at $REDIS_LOG"
    fi
    exit 1
fi
