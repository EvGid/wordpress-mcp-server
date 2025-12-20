#!/bin/bash
# WordPress MCP Server - Production Deployment Script
# Run this on your Ubuntu server

set -e  # Exit on error

echo "=========================================="
echo "WordPress MCP Server - Installation"
echo "=========================================="
echo "Version: 1.3.0 (Ngrok Edition)"
echo "This version switches the tunnel from Cloudflare to Ngrok."
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

# Step 5: Create virtual environment
echo "Step 5: Creating Python virtual environment..."
python3 -m venv venv

# Step 6: Install Python packages
echo "Step 6: Installing Python packages..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Step 7: Test connection
echo "Step 7: Testing WordPress connection..."
python test_server.py

# Step 8: Create systemd service
echo "Step 8: Creating systemd service..."
cat > /etc/systemd/system/wordpress-mcp.service <<'EOF'
[Unit]
Description=WordPress MCP SSE Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/wordpress-mcp-server
Environment=PATH=/opt/wordpress-mcp-server/venv/bin
# Using --sse for ChatGPT MCP compatibility
ExecStart=/opt/wordpress-mcp-server/venv/bin/python mcp_server.py --sse
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Step 9: Enable and start service
echo "Step 9: Starting MCP server..."
systemctl daemon-reload
systemctl enable wordpress-mcp
systemctl restart wordpress-mcp

# Step 10: Check status
echo ""
echo "Step 10: Checking server status..."
sleep 3
systemctl status wordpress-mcp --no-pager

# Step 11: Install ngrok
echo ""
echo "Step 11: Installing ngrok..."
if ! command -v ngrok &> /dev/null; then
    cd /root
    wget -q https://bin.equinox.io/c/bNyj1mQoe3V/ngrok-v3-stable-linux-amd64.tgz
    tar -xzf ngrok-v3-stable-linux-amd64.tgz
    mv ngrok /usr/local/bin/
    rm ngrok-v3-stable-linux-amd64.tgz
fi

# Step 12: Start ngrok
echo "Step 12: Starting ngrok..."
# Kill any existing ngrok
pkill ngrok || true
sleep 2

# Check if authtoken is configured
if ! grep -q "authtoken" /root/.config/ngrok/ngrok.yml 2>/dev/null && [ -z "$NGROK_AUTHTOKEN" ]; then
    echo "⚠️  WARNING: ngrok authtoken not found."
    echo "Please get your FREE authtoken at: https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "Then run: ngrok config add-authtoken <YOUR_TOKEN>"
    echo "And restart this script."
fi

# Run ngrok in the background
nohup ngrok http 8000 --log=stdout > /root/ngrok.log 2>&1 &

echo "Waiting for ngrok to generate a URL (up to 15s)..."
NGROK_URL=""
for i in {1..15}; do
    # Try to get the public URL from the local API
    NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | grep -o 'https://[^"]*\.ngrok-free\.app' | head -n 1)
    if [ ! -z "$NGROK_URL" ]; then
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

# Step 13: Finish
echo ""
echo "=========================================="
echo "✅ INSTALLATION COMPLETE!"
echo "=========================================="

if [ -z "$NGROK_URL" ]; then
    echo "❌ ERROR: Could not retrieve ngrok URL."
    echo "Make sure you added your authtoken: ngrok config add-authtoken YOUR_TOKEN"
    echo "Check logs: cat /root/ngrok.log"
else
    echo "MCP Server is running on port 8000 (SSE Mode)"
    echo ""
    echo "Your NEW URL for ChatGPT (COPY THIS ENTIRE LINE):"
    echo -e "\e[1;32m${NGROK_URL}/sse\e[0m"
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


