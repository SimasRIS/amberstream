"""WSGI entry point for gunicorn.

Importing app runs setup_db() under an app context, so the database and its
seed data exist before the first request is served.

    gunicorn --workers 1 --threads 4 --bind 127.0.0.1:5000 wsgi:app
"""
from app import app

__all__ = ['app']
