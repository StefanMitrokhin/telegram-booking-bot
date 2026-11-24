#!/bin/sh
set -eu
mkdir -p /app/data
chown appuser:appuser /app/data
exec setpriv --reuid=appuser --regid=appuser --init-groups -- python -m booking_bot