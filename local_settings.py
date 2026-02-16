"""Backward-compatible settings module.

Prefer environment variables and `media_organizer.config.Settings`.
This module remains for users with existing local workflows.
"""
from media_organizer.config import Settings

_settings = Settings.from_env()

DOWNLOAD_FOLDER = str(_settings.download_folder)
TV_FOLDER = str(_settings.tv_folder)
MOVIE_FOLDER = str(_settings.movie_folder)
TRASH_FOLDER = str(_settings.trash_folder)
SONARR_API_URL = _settings.sonarr_api_url
SONARR_API_KEY = _settings.sonarr_api_key
SONARR_TV_FOLDER = _settings.sonarr_tv_folder
SONARR_COMMAND_DELAY_SECONDS = _settings.sonarr_command_delay_seconds
TRANSMISSION_HOST = _settings.transmission_host
TRANSMISSION_PORT = _settings.transmission_port
TRANSMISSION_USER = _settings.transmission_user
TRANSMISSION_PASSWORD = _settings.transmission_password
