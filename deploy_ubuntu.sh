#!/bin/bash
# AmberStream Ubuntu Automated Deployment Script
# This script automates the deployment process on Ubuntu

set -e  # Exit on any error

echo "=========================================="
echo "AmberStream Ubuntu Deployment Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get current directory and user
PROJECT_DIR=$(pwd)
CURRENT_USER=$(whoami)
VENV_PATH="$PROJECT_DIR/.venv"

echo "Project directory: $PROJECT_DIR"
echo "Current user: $CURRENT_USER"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Error: Do not run this script as root. Run as regular user with sudo privileges.${NC}"
   exit 1
fi

# Step 1: Update system packages
echo -e "${YELLOW}Step 1: Updating system packages...${NC}"
sudo apt update
sudo apt upgrade -y

# Step 2: Install required system packages
echo -e "${YELLOW}Step 2: Installing required system packages...${NC}"
sudo apt install -y python3 python3-pip python3-venv python3-dev build-essential

# Step 3: Create virtual environment
echo -e "${YELLOW}Step 3: Creating virtual environment...${NC}"
if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists, skipping...${NC}"
fi

# Step 4: Activate virtual environment and install dependencies
echo -e "${YELLOW}Step 4: Installing Python dependencies...${NC}"
source "$VENV_PATH/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Step 5: Create .env file if it doesn't exist
echo -e "${YELLOW}Step 5: Setting up environment variables...${NC}"
if [ ! -f "$PROJECT_DIR/.env" ]; then
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "SECRET_KEY=$SECRET_KEY" > "$PROJECT_DIR/.env"
    echo -e "${GREEN}✓ Created .env file with generated SECRET_KEY${NC}"
    echo -e "${YELLOW}⚠ IMPORTANT: Keep your .env file secure and never commit it!${NC}"
else
    echo -e "${YELLOW}.env file already exists, skipping...${NC}"
fi

# Step 6: Create instance directory if it doesn't exist
echo -e "${YELLOW}Step 6: Setting up directories...${NC}"
mkdir -p "$PROJECT_DIR/instance"
chmod 755 "$PROJECT_DIR/instance"
echo -e "${GREEN}✓ Directories configured${NC}"

# Step 7: Create systemd service file
echo -e "${YELLOW}Step 7: Creating systemd service...${NC}"
SERVICE_FILE="/etc/systemd/system/amberstream.service"

# Check if service already exists
if [ -f "$SERVICE_FILE" ]; then
    echo -e "${YELLOW}Service file already exists.${NC}"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Skipping service file creation...${NC}"
    else
        sudo rm "$SERVICE_FILE"
    fi
fi

if [ ! -f "$SERVICE_FILE" ]; then
    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=AmberStream Flask Application
After=network.target

[Service]
Type=notify
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_PATH/bin"
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$VENV_PATH/bin/gunicorn -c gunicorn_config.py app:app
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=10
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
    echo -e "${GREEN}✓ Systemd service file created${NC}"
fi

# Step 8: Reload systemd and enable service
echo -e "${YELLOW}Step 8: Enabling systemd service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable amberstream.service
echo -e "${GREEN}✓ Service enabled${NC}"

# Step 9: Configure firewall
echo -e "${YELLOW}Step 9: Configuring firewall...${NC}"
if command -v ufw &> /dev/null; then
    # Check if UFW is active
    if sudo ufw status | grep -q "Status: active"; then
        echo -e "${YELLOW}UFW is already active${NC}"
    else
        echo -e "${YELLOW}Enabling UFW...${NC}"
        echo "y" | sudo ufw --force enable
    fi
    
    # Allow SSH (critical!)
    sudo ufw allow 22/tcp > /dev/null 2>&1 || true
    
    # Allow port 8000 (Gunicorn)
    sudo ufw allow 8000/tcp
    echo -e "${GREEN}✓ Firewall configured (port 8000 allowed)${NC}"
else
    echo -e "${YELLOW}UFW not found, skipping firewall configuration${NC}"
fi

# Step 10: Ask about starting the service
echo ""
echo -e "${YELLOW}Step 10: Service management${NC}"
read -p "Do you want to start the service now? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    sudo systemctl start amberstream.service
    sleep 2
    
    # Check service status
    if sudo systemctl is-active --quiet amberstream.service; then
        echo -e "${GREEN}✓ Service started successfully!${NC}"
    else
        echo -e "${RED}✗ Service failed to start. Check logs with: sudo journalctl -u amberstream -n 50${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}Service created but not started. Start it manually with: sudo systemctl start amberstream${NC}"
fi

# Step 11: Optional - Ask about Nginx
echo ""
read -p "Do you want to set up Nginx reverse proxy? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Setting up Nginx...${NC}"
    
    # Install Nginx if not installed
    if ! command -v nginx &> /dev/null; then
        sudo apt install -y nginx
    fi
    
    # Create Nginx configuration
    NGINX_CONFIG="/etc/nginx/sites-available/amberstream"
    
    read -p "Enter your domain name (or press Enter to use IP address): " DOMAIN_NAME
    if [ -z "$DOMAIN_NAME" ]; then
        DOMAIN_NAME="_"
    fi
    
    sudo tee "$NGINX_CONFIG" > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN_NAME;
    
    client_max_body_size 10M;

    location /static {
        alias $PROJECT_DIR/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
EOF
    
    # Enable site
    sudo ln -sf "$NGINX_CONFIG" /etc/nginx/sites-enabled/amberstream
    sudo rm -f /etc/nginx/sites-enabled/default
    
    # Test and restart Nginx
    if sudo nginx -t; then
        sudo systemctl restart nginx
        sudo ufw allow 80/tcp
        sudo ufw allow 443/tcp
        echo -e "${GREEN}✓ Nginx configured and started${NC}"
        echo -e "${YELLOW}You can now access your site via http://${DOMAIN_NAME}${NC}"
    else
        echo -e "${RED}✗ Nginx configuration test failed${NC}"
    fi
fi

# Summary
echo ""
echo "=========================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Service Management:"
echo "  Start:   sudo systemctl start amberstream"
echo "  Stop:    sudo systemctl stop amberstream"
echo "  Restart: sudo systemctl restart amberstream"
echo "  Status:  sudo systemctl status amberstream"
echo "  Logs:    sudo journalctl -u amberstream -f"
echo ""
echo "Access your application:"
SERVER_IP=$(hostname -I | awk '{print $1}')
echo "  Direct:  http://$SERVER_IP:8000"
if [ -f "/etc/nginx/sites-enabled/amberstream" ]; then
    echo "  Via Nginx: http://$SERVER_IP (or your domain)"
fi
echo ""
echo "Important files:"
echo "  Service config: /etc/systemd/system/amberstream.service"
echo "  Environment:    $PROJECT_DIR/.env"
echo "  Project path:   $PROJECT_DIR"
echo ""
echo -e "${YELLOW}⚠ Remember to:${NC}"
echo "  1. Keep your .env file secure (SECRET_KEY)"
echo "  2. Set up regular backups of instance/plans.db"
echo "  3. Configure SSL/HTTPS for production"
echo ""

