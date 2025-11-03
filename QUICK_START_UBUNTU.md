# Quick Start: Deploy on Ubuntu

## Fastest Method (Automated Script)

1. **Transfer files to Ubuntu server:**
   ```bash
   # Using scp
   scp -r . username@your-server-ip:/home/username/powergrid
   
   # Or using rsync (better for updates)
   rsync -avz --exclude '.venv' --exclude 'instance' . username@your-server-ip:/home/username/powergrid/
   ```

2. **SSH into Ubuntu server:**
   ```bash
   ssh username@your-server-ip
   ```

3. **Run deployment script:**
   ```bash
   cd ~/powergrid
   chmod +x deploy_ubuntu.sh
   ./deploy_ubuntu.sh
   ```

4. **Access your app:**
   - Direct: `http://your-server-ip:8000`
   - Or via domain if you set up Nginx

That's it! 🚀

## Manual Method (3 Steps)

```bash
# 1. Install dependencies and create virtual environment
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Create .env file with SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"  # Copy output
nano .env  # Add: SECRET_KEY=your-generated-key-here

# 3. Start with Gunicorn
gunicorn -c gunicorn_config.py app:app
```

## Production Setup (with systemd)

See `UBUNTU_DEPLOYMENT.md` for complete instructions including:
- Systemd service (auto-start on boot)
- Nginx reverse proxy
- SSL/HTTPS setup
- Security best practices

## Files You Need

- ✅ `app.py` - Main application
- ✅ `requirements.txt` - Python dependencies
- ✅ `gunicorn_config.py` - Gunicorn configuration
- ✅ `static/` folder - CSS, images
- ✅ `templates/` folder - HTML templates
- ✅ `deploy_ubuntu.sh` - Automated deployment script

## Common Commands After Deployment

```bash
# Service management
sudo systemctl start amberstream      # Start
sudo systemctl stop amberstream      # Stop
sudo systemctl restart amberstream    # Restart
sudo systemctl status amberstream    # Check status

# View logs
sudo journalctl -u amberstream -f    # Follow logs
sudo journalctl -u amberstream -n 50 # Last 50 lines
```

## Troubleshooting

**Service won't start?**
```bash
sudo journalctl -u amberstream -n 50  # Check logs
sudo systemctl status amberstream      # Check status
```

**Can't access from browser?**
```bash
sudo ufw status                        # Check firewall
sudo ss -tlnp | grep 8000             # Check if port is listening
curl http://localhost:8000             # Test locally
```

For more details, see `UBUNTU_DEPLOYMENT.md`

