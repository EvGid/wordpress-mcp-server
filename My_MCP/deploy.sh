#!/bin/bash
# WordPress MCP Server - Production Deployment Script
# Run this on your Ubuntu server

set -e  # Exit on error

echo "=========================================="
echo "WordPress MCP Server - Installation"
echo "=========================================="
echo ""

# Step 1: Update system
echo "Step 1: Updating system..."
apt update && apt upgrade -y

# Step 2: Install dependencies
echo "Step 2: Installing dependencies..."
apt install -y python3 python3-pip python3-venv git curl wget

# Step 3: Create project directory
echo "Step 3: Creating project directory..."
mkdir -p /opt/wordpress-mcp-server
cd /opt/wordpress-mcp-server

# Step 4: Clone repository
echo "Step 4: Cloning repository from GitHub..."
if [ -d ".git" ]; then
    echo "Repository already exists, pulling latest changes..."
    git pull origin main
else
    git clone https://github.com/EvGid/wordpress-mcp-server.git .
fi

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
Description=WordPress MCP Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/wordpress-mcp-server/My_MCP
Environment=PATH=/opt/wordpress-mcp-server/My_MCP/venv/bin
ExecStart=/opt/wordpress-mcp-server/My_MCP/venv/bin/python mcp_server.py --http
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
systemctl start wordpress-mcp

# Step 11: Check status
echo ""
echo "Step 11: Checking server status..."
sleep 3
systemctl status wordpress-mcp --no-pager

# Step 12: Install Cloudflare Tunnel
echo ""
echo "Step 12: Installing Cloudflare Tunnel..."
cd /root
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared-linux-amd64
mv cloudflared-linux-amd64 /usr/local/bin/cloudflared

# Step 13: Start Cloudflare Tunnel
echo "Step 13: Starting Cloudflare Tunnel..."
nohup cloudflared tunnel --url http://localhost:8000 > /root/cloudflared.log 2>&1 &
sleep 5

# Step 14: Get HTTPS URL
echo ""
echo "=========================================="
echo "✅ INSTALLATION COMPLETE!"
echo "=========================================="
echo ""
echo "MCP Server is running on port 8000"
echo ""
echo "Your HTTPS URL for ChatGPT:"
grep -o 'https://[^ ]*' /root/cloudflared.log | head -1
echo ""
echo "Management commands:"
echo "  Status:  systemctl status wordpress-mcp"
echo "  Logs:    journalctl -u wordpress-mcp -f"
echo "  Restart: systemctl restart wordpress-mcp"
echo ""
echo "Cloudflare Tunnel log: /root/cloudflared.log"
echo "=========================================="
