"""
Configuration loaded from environment variables with sensible defaults.

DOCKER USAGE:
  Set environment variables in docker-compose.yml (see README for examples)

LOCAL DEVELOPMENT:
  Option 1: Set environment variables in your shell
    export DOWNLOAD_FOLDER=/path/to/downloads
    export TV_FOLDER=/path/to/tv
    python runner.py

  Option 2: Temporarily modify this file with hardcoded values
    (Just don't commit your changes)

  Option 3: Create local_settings_local.py and modify runner.py import
    (For persistent local config without affecting this file)
"""
import os

# Folder paths - adjust based on your mount point
DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER', '/media/downloads')
TV_FOLDER = os.getenv('TV_FOLDER', '/media/tv')
MOVIE_FOLDER = os.getenv('MOVIE_FOLDER', '/media/movies')
TRASH_FOLDER = os.getenv('TRASH_FOLDER', '/media/trash')

# Sonarr configuration
SONARR_API_URL = os.getenv('SONARR_API_URL', 'http://localhost:8989/api/v3')
SONARR_API_KEY = os.getenv('SONARR_API_KEY', '')
SONARR_TV_FOLDER = os.getenv('SONARR_TV_FOLDER', '/media/tv/')  # May differ from TV_FOLDER if Sonarr is in Docker

# Transmission configuration
TRANSMISSION_HOST = os.getenv('TRANSMISSION_HOST', 'localhost')
TRANSMISSION_PORT = int(os.getenv('TRANSMISSION_PORT', '9091'))
TRANSMISSION_USER = os.getenv('TRANSMISSION_USER', '')
TRANSMISSION_PASSWORD = os.getenv('TRANSMISSION_PASSWORD', '')
