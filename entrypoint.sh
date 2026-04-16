#!/bin/bash
set -e

# Write env vars to a file so cron/server can source them
ENV_FILE="/app/.env.cron"
cat > "$ENV_FILE" <<EOF
export COOKIE='$(echo "$COOKIE" | sed "s/'/'\\\\''/g")'
export TOKEN='$(echo "$TOKEN" | sed "s/'/'\\\\''/g")'
export WEBHOOK_URL='$(echo "$WEBHOOK_URL" | sed "s/'/'\\\\''/g")'
export NOTIFY_URL='$(echo "$NOTIFY_URL" | sed "s/'/'\\\\''/g")'
export AUTO_LAST_WEEK='${AUTO_LAST_WEEK:-1}'
export CRON_SCHEDULE='${CRON_SCHEDULE:-0 3 * * 3}'
export RUN_ONCE='${RUN_ONCE:-0}'
EOF

# Ensure output directory exists
mkdir -p /app/output

# Start the Flask server in background
. "$ENV_FILE"
/usr/local/bin/python server.py &
SERVER_PID=$!

echo "[ENTRYPOINT] Flask server started (PID: $SERVER_PID)"

# Wait for server process to keep container alive
wait $SERVER_PID
