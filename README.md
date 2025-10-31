# AmberStream Energy

A Flask-based web application for managing hydroelectricity plans and prices.

## Features

- Public-facing website for electricity plans
- Worker/admin login system
- Dynamic price management
- Real-time price updates on the website

## Tech Stack

- Flask (Python web framework)
- SQLite (Database)
- SQLAlchemy (ORM)
- Flask-Login (Authentication)
- Gunicorn (Production server)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/SimasRIS/amberstream.git
cd amberstream
```

2. Create virtual environment:
```bash
python3 -m venv .venv
```

3. Activate virtual environment:
```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux/Mac
source .venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Run the application:
```bash
python app.py
```

## Default Login Credentials

- Username: `admin`
- Password: `admin123`

**⚠️ IMPORTANT: Change these credentials in production!**

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed production deployment instructions.

## Project Structure

```
amberstream/
├── app.py                 # Flask application
├── requirements.txt       # Python dependencies
├── gunicorn_config.py     # Gunicorn configuration
├── static/               # CSS, images, static files
├── templates/            # HTML templates
└── instance/             # Database files (auto-created)
```

## License

This project is for educational/exercise purposes.

