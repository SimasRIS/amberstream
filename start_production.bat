@echo off
REM Production startup script for AmberStream (Windows)
REM Usage: start_production.bat

REM Activate virtual environment if it exists
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

REM Set production secret key (CHANGE THIS IN PRODUCTION!)
set SECRET_KEY=change-this-to-a-secure-random-key-in-production

REM Start Gunicorn
gunicorn -c gunicorn_config.py app:app

pause

