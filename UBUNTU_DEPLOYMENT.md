# AmberStream Ubuntu Deployment Guide

Complete step-by-step guide for deploying AmberStream on Ubuntu Server.

## Prerequisites

- Ubuntu 20.04 LTS or later (recommended: 22.04 LTS or 24.04 LTS)
- SSH access to your Ubuntu server
- Root or sudo privileges
- (Optional) Domain name pointed to your server IP

---

## Method 1: Automated Deployment Script (Recommended)

### Quick Start

1. **Transfer files to Ubuntu server:**
   ```bash
   # From your local machine, copy all project files to Ubuntu server
   scp -r . username@your-server-ip:/home/username/powergrid
   # Or use rsync
   rsync -avz . username@your-server-ip:/home/username/powergrid/
   ```

2. **SSH into your Ubuntu server:**
   ```bash
   ssh username@your-server-ip
   ```

3. **Run the deployment script:**
   ```bash
   cd ~/powergrid
   chmod +x deploy_ubuntu.sh
   ./deploy_ubuntu.sh
   ```

The script will:
- Install Python 3, pip, and venv
- Create a virtual environment
- Install all dependencies
- Set up systemd service
- Configure firewall
- Generate a secure SECRET_KEY

---

## Method 2: Manual Deployment

### Step 1: Update System

```bash
sudo apt update
sudo apt upgrade -y
```

### Step 2: Install Python and Required Packages

```bash
# Install Python 3 and pip
sudo apt install python3 python3-pip python3-venv python3-dev -y

# Install build essentials (for compiling some Python packages)
sudo apt install build-essential -y
```

### Step 3: Create Project Directory and Set Up Virtual Environment

```bash
# Navigate to your home directory or desired location
cd ~

# If you haven't copied files yet, create directory and copy files here
mkdir -p powergrid
cd powergrid

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### Step 4: Install Python Dependencies

```bash
# Make sure you're in the project directory with requirements.txt
pip install -r requirements.txt

# Verify installation
pip list
```

### Step 5: Generate and Set SECRET_KEY

```bash
# Generate a secure secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Copy the output, then create environment file
nano ~/powergrid/.env
```

Add to `.env` file:
```
SECRET_KEY=your-generated-secret-key-here
```

**Important:** Keep this file secure and never commit it to version control!

### Step 6: Set Up Systemd Service (Auto-start on boot)

```bash
sudo nano /etc/systemd/system/amberstream.service
```

Paste the following (adjust paths for your setup):

```ini
[Unit]
Description=AmberStream Flask Application
After=network.target

[Service]
Type=notify
User=YOUR_USERNAME
Group=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/powergrid
Environment="PATH=/home/YOUR_USERNAME/powergrid/.venv/bin"
EnvironmentFile=/home/YOUR_USERNAME/powergrid/.env
ExecStart=/home/YOUR_USERNAME/powergrid/.venv/bin/gunicorn -c gunicorn_config.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

**Replace:**
- `YOUR_USERNAME` with your actual username (run `whoami` to check)
- Adjust `/home/YOUR_USERNAME/powergrid` if your project is in a different location

### Step 7: Enable and Start Service

```bash
# Reload systemd daemon
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable amberstream

# Start the service
sudo systemctl start amberstream

# Check status
sudo systemctl status amberstream

# View logs
sudo journalctl -u amberstream -f
```

### Step 8: Configure Firewall (UFW)

```bash
# Enable UFW if not already enabled
sudo ufw --force enable

# Allow SSH (important - do this first!)
sudo ufw allow 22/tcp

# Allow HTTP traffic on port 8000
sudo ufw allow 8000/tcp

# If using Nginx (recommended), allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Check firewall status
sudo ufw status
```

### Step 9: Verify Deployment

```bash
# Check if the service is running
sudo systemctl status amberstream

# Check if port 8000 is listening
sudo netstat -tlnp | grep 8000
# or
sudo ss -tlnp | grep 8000

# Test locally on server
curl http://localhost:8000
```

Visit in browser: `http://your-server-ip:8000`

---

## Method 3: Using Nginx as Reverse Proxy (Recommended for Production)

This setup allows you to:
- Use standard HTTP (80) and HTTPS (443) ports
- Add SSL/HTTPS easily
- Serve static files efficiently
- Better security and performance

### Install Nginx

```bash
sudo apt install nginx -y
```

### Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/amberstream
```

Add the following configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;  # Replace with your domain or use _ for all
    
    # Increase client body size if needed
    client_max_body_size 10M;

    # Serve static files directly
    location /static {
        alias /home/YOUR_USERNAME/powergrid/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Proxy all other requests to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # WebSocket support (if needed in future)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

**Replace `YOUR_USERNAME` with your actual username.**

### Enable Site

```bash
# Create symlink to enable site
sudo ln -s /etc/nginx/sites-available/amberstream /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

### Set Up SSL with Let's Encrypt (Recommended)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get SSL certificate (replace with your domain)
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Certbot will automatically configure Nginx for HTTPS
# Certificates auto-renew via cron job
```

Now your site will be accessible via `https://your-domain.com`

---

## Managing the Service

### Common Commands

```bash
# Start service
sudo systemctl start amberstream

# Stop service
sudo systemctl stop amberstream

# Restart service
sudo systemctl restart amberstream

# Reload service (without downtime)
sudo systemctl reload amberstream

# Check status
sudo systemctl status amberstream

# View logs
sudo journalctl -u amberstream -f

# View last 100 lines of logs
sudo journalctl -u amberstream -n 100

# Disable auto-start on boot
sudo systemctl disable amberstream

# Enable auto-start on boot
sudo systemctl enable amberstream
```

### Updating the Application

```bash
# SSH into server
ssh username@your-server-ip

# Navigate to project directory
cd ~/powergrid

# Pull latest code (if using git) or copy new files
# git pull  # if using git

# Activate virtual environment
source .venv/bin/activate

# Install new dependencies (if requirements.txt changed)
pip install -r requirements.txt

# Restart service
sudo systemctl restart amberstream

# Check status
sudo systemctl status amberstream
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check service status for errors
sudo systemctl status amberstream

# Check logs for detailed error messages
sudo journalctl -u amberstream -n 50

# Verify paths in service file
sudo cat /etc/systemd/system/amberstream.service

# Test Gunicorn manually
cd ~/powergrid
source .venv/bin/activate
gunicorn -c gunicorn_config.py app:app
```

### Permission Errors

```bash
# Make sure your user owns the project directory
sudo chown -R $USER:$USER ~/powergrid

# Ensure instance folder is writable
chmod 755 ~/powergrid/instance
chmod 664 ~/powergrid/instance/plans.db  # if exists
```

### Port Already in Use

```bash
# Find what's using port 8000
sudo lsof -i :8000
# or
sudo ss -tlnp | grep 8000

# Kill the process (replace PID with actual process ID)
sudo kill -9 <PID>

# Or change port in gunicorn_config.py
```

### Database Issues

```bash
# Database auto-creates at instance/plans.db
# Ensure instance folder exists and is writable
mkdir -p ~/powergrid/instance
chmod 755 ~/powergrid/instance

# Check database file permissions
ls -la ~/powergrid/instance/
```

### Nginx Errors

```bash
# Test Nginx configuration
sudo nginx -t

# Check Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Check if Nginx is running
sudo systemctl status nginx
```

### Can't Access from Browser

1. **Check firewall:**
   ```bash
   sudo ufw status
   ```

2. **Check if service is running:**
   ```bash
   sudo systemctl status amberstream
   ```

3. **Test locally on server:**
   ```bash
   curl http://localhost:8000
   ```

4. **Check server IP:**
   ```bash
   ip addr show
   ```

5. **Verify port is listening:**
   ```bash
   sudo netstat -tlnp | grep 8000
   ```

---

## Security Best Practices

### 1. Use Strong SECRET_KEY
- Generate using: `python3 -c "import secrets; print(secrets.token_hex(32))"`
- Store in `.env` file (not in code)
- Never commit `.env` to version control

### 2. Firewall Configuration
```bash
# Only allow necessary ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (if using Nginx)
sudo ufw allow 443/tcp   # HTTPS (if using SSL)
sudo ufw enable
```

### 3. Run as Non-Root User
- Always run the service as a regular user (not root)
- Use your regular user account in systemd service file

### 4. Keep System Updated
```bash
sudo apt update
sudo apt upgrade -y
```

### 5. Use HTTPS
- Always use SSL/TLS certificates (Let's Encrypt is free)
- Redirect HTTP to HTTPS in Nginx configuration

### 6. Regular Backups
```bash
# Create backup script
nano ~/backup_amberstream.sh
```

Add:
```bash
#!/bin/bash
BACKUP_DIR="/home/YOUR_USERNAME/backups"
mkdir -p $BACKUP_DIR
cp ~/powergrid/instance/plans.db $BACKUP_DIR/plans_$(date +%Y%m%d_%H%M%S).db
# Keep only last 7 days
find $BACKUP_DIR -name "plans_*.db" -mtime +7 -delete
```

Make executable and add to crontab:
```bash
chmod +x ~/backup_amberstream.sh
crontab -e
# Add: 0 2 * * * /home/YOUR_USERNAME/backup_amberstream.sh
```

---

## File Structure on Ubuntu

```
/home/YOUR_USERNAME/powergrid/
├── .venv/                    # Virtual environment
├── .env                      # Environment variables (SECRET_KEY)
├── app.py                    # Main application
├── gunicorn_config.py        # Gunicorn configuration
├── requirements.txt          # Python dependencies
├── start_production.sh       # Startup script
├── deploy_ubuntu.sh          # Deployment script
├── instance/
│   └── plans.db             # SQLite database (auto-created)
├── static/                  # Static files (CSS, images)
└── templates/               # HTML templates
```

---

## Quick Reference

| Task | Command |
|------|---------|
| View service status | `sudo systemctl status amberstream` |
| View logs | `sudo journalctl -u amberstream -f` |
| Restart service | `sudo systemctl restart amberstream` |
| Stop service | `sudo systemctl stop amberstream` |
| Start service | `sudo systemctl start amberstream` |
| Test Nginx config | `sudo nginx -t` |
| Restart Nginx | `sudo systemctl restart nginx` |
| Check firewall | `sudo ufw status` |
| Check open ports | `sudo ss -tlnp` |

---

## Support

If you encounter issues:
1. Check service logs: `sudo journalctl -u amberstream -n 50`
2. Verify all paths in systemd service file
3. Ensure firewall allows necessary ports
4. Check file permissions
5. Verify Python virtual environment is activated in service

---

**Your AmberStream application should now be running on Ubuntu!** 🚀

