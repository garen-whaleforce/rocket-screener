#!/bin/bash
# Rocket Screener - Cron Setup Script
# v10 Deployment Configuration
#
# This script sets up the daily cron job for the newsletter pipeline.
# Run time: 08:00 Taiwan time (UTC+8), Monday-Friday

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Rocket Screener Cron Setup ==="
echo "Project directory: $PROJECT_DIR"

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    CRON_FILE="/tmp/rocket-screener-crontab"
else
    CRON_FILE="/etc/cron.d/rocket-screener"
fi

# Create cron entry
# 08:00 Taiwan (UTC+8) = 00:00 UTC
# Adjust if your server is not in UTC
CRON_SCHEDULE="0 0 * * 1-5"  # 00:00 UTC = 08:00 Taiwan

cat > "$CRON_FILE" << EOF
# Rocket Screener Daily Newsletter
# Runs at 08:00 Taiwan time (00:00 UTC), Monday-Friday
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
PYTHONPATH=$PROJECT_DIR

$CRON_SCHEDULE cd $PROJECT_DIR && /usr/bin/python3 -m app.run >> $PROJECT_DIR/logs/cron.log 2>&1
EOF

# Install crontab
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS: add to user crontab
    crontab -l 2>/dev/null > /tmp/current_cron || true
    grep -v "rocket-screener" /tmp/current_cron > /tmp/new_cron || true
    echo "$CRON_SCHEDULE cd $PROJECT_DIR && /usr/bin/python3 -m app.run >> $PROJECT_DIR/logs/cron.log 2>&1" >> /tmp/new_cron
    crontab /tmp/new_cron
    echo "Cron job installed for current user"
else
    # Linux: install to /etc/cron.d
    sudo chmod 644 "$CRON_FILE"
    echo "Cron job installed at $CRON_FILE"
fi

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

echo ""
echo "=== Setup Complete ==="
echo "Cron schedule: $CRON_SCHEDULE (00:00 UTC = 08:00 Taiwan)"
echo "Log file: $PROJECT_DIR/logs/cron.log"
echo ""
echo "To verify cron:"
echo "  crontab -l"
echo ""
echo "To run manually:"
echo "  cd $PROJECT_DIR && python -m app.run"
