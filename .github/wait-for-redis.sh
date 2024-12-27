#!/usr/bin/env bash

set -e

REDIS_HOST="$1"
REDIS_PORT="$2"

shift

redis-cli --version

until redis-cli -h $REDIS_HOST -p $REDIS_PORT ping
do
  >&2 echo "Redis is un-connectable - sleeping"
  sleep 5
done

>&2 echo "Redis is up!"
