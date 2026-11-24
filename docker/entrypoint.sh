#!/bin/sh
set -eu
mkdir -p /app/data
chown appuser:appuser /app/data
if [ "$#" -eq 0 ]; then
  set -- python -m booking_bot
fi
exec setpriv --reuid=appuser --regid=appuser --init-groups -- "$@"