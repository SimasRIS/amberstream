#!/bin/bash
# Production startup script for AmberStream
# Usage: ./start_production.sh

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Set production secret key (CHANGE THIS IN PRODUCTION!)
export SECRET_KEY='change-this-to-a-secure-random-key-in-production'

# Start Gunicorn
gunicorn -c gunicorn_config.py app:app

