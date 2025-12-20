#!/bin/bash
# WordPress MCP Server - Production Deployment Script
# Run this on your Ubuntu server

set -e  # Exit on error

echo "=========================================="
echo "WordPress MCP Server - Installation"
echo "=========================================="
echo "Version: 1.0.7 (Security Patch Mode)"
echo "This version bypasses the 421 Misdirected Request error."
echo ""



# Step 1: Update system
echo "Step 1: Updating system..."
apt update && apt upgrade -y

# Step 2: Install dependencies
echo "Step 2: Installing dependencies..."
apt install -y python3 python3-pip python3-venv git curl wget

# Step 3: Clean Start
echo "Step 3: Wiping old directory for a clean install..."
rm -rf /opt/wordpress-mcp-server
mkdir -p /opt/wordpress-mcp-server
cd /opt/wordpress-mcp-server

# Step 4: Clone repository
echo "Step 4: Cloning fresh repository from GitHub..."
git clone https://github.com/EvGid/wordpress-mcp-server.git .



# Step 5: Navigate to My_MCP
echo "Step 5: Setting up My_MCP..."
cd My_MCP

# Step 6: Create virtual environment
echo "Step 6: Creating Python virtual environment..."
python3 -m venv venv

# Step 7: Install Python packages
echo "Step 7: Installing Python packages..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Step 8: Test connection
echo "Step 8: Testing WordPress connection..."
python test_server.py

# Step 9: Create systemd service
echo "Step 9: Creating systemd service..."
cat > /etc/systemd/system/wordpress-mcp.service <<'EOF'
[Unit]
Description=WordPress MCP SSE Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/wordpress-mcp-server/My_MCP
Environment=PATH=/opt/wordpress-mcp-server/My_MCP/venv/bin
# Using --sse for ChatGPT MCP compatibility
ExecStart=/opt/wordpress-mcp-server/My_MCP/venv/bin/python mcp_server.py --sse
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Step 10: Enable and start service
echo "Step 10: Starting MCP server..."
systemctl daemon-reload
systemctl enable wordpress-mcp
systemctl restart wordpress-mcp

# Step 11: Check status
echo ""
echo "Step 11: Checking server status..."
sleep 3
systemctl status wordpress-mcp --no-pager

# Step 12: Install Cloudflare Tunnel
echo ""
echo "Step 12: Installing Cloudflare Tunnel..."
if [ ! -f "/usr/local/bin/cloudflared" ]; then
    cd /root
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
    chmod +x cloudflared-linux-amd64
    mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
fi

# Step 13: Start Cloudflare Tunnel
echo "Step 13: Starting Cloudflare Tunnel..."
# Kill any existing cloudflared to avoid port conflicts
pkill cloudflared || true
sleep 2

# Clear old logs to ensure we get exactly the fresh URL
> /root/cloudflared.log

# Run cloudflared. --no-chunked-encoding helps with some proxy issues.
nohup cloudflared tunnel --url http://127.0.0.1:8000 --no-chunked-encoding > /root/cloudflared.log 2>&1 &

echo "Waiting for Cloudflare Tunnel to generate a new URL (up to 30s)..."
TUNNEL_URL=""
for i in {1..30}; do
    # Use grep -oa because cloudflared logs sometimes contain binary/control characters
    TUNNEL_URL=$(grep -oa 'https://[^ ]*\.trycloudflare\.com' /root/cloudflared.log | tail -n 1)
    if [ ! -z "$TUNNEL_URL" ]; then
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

# Step 14: Get HTTPS URL
echo ""
echo "=========================================="
echo "✅ INSTALLATION COMPLETE!"
echo "=========================================="

if [ -z "$TUNNEL_URL" ]; then
    echo "❌ ERROR: Could not retrieve Tunnel URL."
    echo "Check logs manually: cat /root/cloudflared.log"
else
    echo "MCP Server is running on port 8000 (SSE Mode)"
    echo ""
    echo "Your NEW URL for ChatGPT (COPY THIS ENTIRE LINE):"
    echo -e "\e[1;32m${TUNNEL_URL}/sse\e[0m"
    echo ""
    echo "IMPORTANT: The old link is no longer valid. You MUST update it in ChatGPT."
    echo "In ChatGPT settings, use Authentication: None"
fi

echo ""
echo "Management commands:"
echo "  Status:  systemctl status wordpress-mcp"
echo "  Logs:    journalctl -u wordpress-mcp -n 50 --no-pager"
echo "  Restart: systemctl restart wordpress-mcp"
echo "=========================================="

echo ""
echo "DEBUG - Fresh Server Logs (Checking Patch Status):"
journalctl -u wordpress-mcp -n 20 --no-pager | grep "patch" || echo "Note: Patch message not found in first 20 lines, check logs manually."


