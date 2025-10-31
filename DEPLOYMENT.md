# AmberStream Production Deployment Guide

## Quick Start

### 1. Prepare Your Project
```bash
# Make sure all files are in place:
# - app.py
# - requirements.txt
# - templates/ (folder)
# - static/ (folder)
```

### 2. On Your Server/Virtual Machine

#### Install Python and Dependencies
```bash
# Install Python 3.8+ if not already installed
sudo apt update
sudo apt install python3 python3-pip python3-venv -y  # Ubuntu/Debian
# OR
sudo yum install python3 python3-pip -y  # CentOS/RHEL

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### Set Environment Variables
```bash
# Generate a secure secret key (run this and copy the output)
python3 -c "import secrets; print(secrets.token_hex(32))"

# Set it as environment variable
export SECRET_KEY='your-generated-secret-key-here'

# Or add to ~/.bashrc for persistence:
echo "export SECRET_KEY='your-generated-secret-key-here'" >> ~/.bashrc
source ~/.bashrc
```

#### Run Production Server
```bash
# Option 1: Using the startup script
chmod +x start_production.sh
./start_production.sh

# Option 2: Direct Gunicorn command
gunicorn -c gunicorn_config.py app:app

# Option 3: Simple Gunicorn (no config file)
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### 3. Configure Firewall
```bash
# Allow port 8000 (or your chosen port)
sudo ufw allow 8000/tcp  # Ubuntu/Debian
sudo firewall-cmd --add-port=8000/tcp --permanent && sudo firewall-cmd --reload  # CentOS/RHEL
```

### 4. Access Your Site
Visit: `http://your-server-ip:8000/`

---

## Advanced: Run as a System Service (Auto-start on boot)

### Create Systemd Service
```bash
sudo nano /etc/systemd/system/amberstream.service
```

Add this content (adjust paths):
```ini
[Unit]
Description=AmberStream Flask App
After=network.target

[Service]
User=your-username
Group=your-group
WorkingDirectory=/home/your-username/amberstream
Environment="PATH=/home/your-username/amberstream/.venv/bin"
Environment="SECRET_KEY=your-secret-key-here"
ExecStart=/home/your-username/amberstream/.venv/bin/gunicorn -c gunicorn_config.py app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable and Start
```bash
sudo systemctl daemon-reload
sudo systemctl enable amberstream
sudo systemctl start amberstream

# Check status
sudo systemctl status amberstream

# View logs
sudo journalctl -u amberstream -f
```

---

## Using Nginx as Reverse Proxy (Recommended)

### Install Nginx
```bash
sudo apt install nginx -y  # Ubuntu/Debian
sudo yum install nginx -y  # CentOS/RHEL
```

### Configure Nginx
```bash
sudo nano /etc/nginx/sites-available/amberstream
```

Add:
```nginx
server {
    listen 80;
    server_name your-domain.com;  # or your IP

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /home/your-username/amberstream/static;
        expires 30d;
    }
}
```

Enable and restart:
```bash
sudo ln -s /etc/nginx/sites-available/amberstream /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl restart nginx
```

Now access via: `http://your-domain.com` or `http://your-ip`

---

## Troubleshooting

### Port already in use?
```bash
# Find process using port 8000
sudo lsof -i :8000
# Kill it
sudo kill -9 <PID>
```

### Permission errors?
```bash
# Make sure your user owns the project directory
sudo chown -R $USER:$USER /path/to/your/project
```

### Database issues?
```bash
# The database will be created automatically at instance/plans.db
# Make sure the instance/ folder is writable
chmod 755 instance
```

---

## Security Checklist

- [ ] Change SECRET_KEY to a strong random value
- [ ] Set DEBUG=False in production (already done)
- [ ] Use HTTPS/SSL certificate (Let's Encrypt)
- [ ] Configure firewall properly
- [ ] Keep Python and dependencies updated
- [ ] Use a non-root user to run the app
- [ ] Set up regular backups of `instance/plans.db`

---

## Project Structure for Deployment

```
amberstream/
├── app.py
├── requirements.txt
├── gunicorn_config.py
├── start_production.sh
├── instance/
│   └── plans.db (auto-created)
├── static/
│   ├── style.css
│   ├── amberstream.png
│   ├── amberstreamhq.jpg
│   └── ... (other images)
└── templates/
    ├── AmberStream.html
    ├── about.html
    ├── plans.html
    └── ... (other templates)
```

