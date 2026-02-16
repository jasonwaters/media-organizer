from pathlib import Path

import pytest

from media_organizer.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        download_folder=tmp_path / "downloads",
        tv_folder=tmp_path / "tv",
        movie_folder=tmp_path / "movies",
        trash_folder=tmp_path / "trash",
        sonarr_api_url="http://sonarr:8989/api/v3",
        sonarr_api_key="key123",
        sonarr_tv_folder="/library/tv",
        transmission_host="localhost",
        transmission_port=9091,
        transmission_user="",
        transmission_password="",
    )
