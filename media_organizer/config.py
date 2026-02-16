from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    download_folder: Path
    tv_folder: Path
    movie_folder: Path
    trash_folder: Path
    sonarr_api_url: str
    sonarr_api_key: str
    sonarr_tv_folder: str
    transmission_host: str
    transmission_port: int
    transmission_user: str
    transmission_password: str
    video_file_size_minimum: int = 10_000_000
    sonarr_command_delay_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.transmission_port <= 0:
            raise ValueError(f"TRANSMISSION_PORT must be a positive integer, got {self.transmission_port}")

        if self.sonarr_command_delay_seconds < 0:
            raise ValueError(
                f"SONARR_COMMAND_DELAY_SECONDS must be >= 0, got {self.sonarr_command_delay_seconds}"
            )

        normalized_api_url = self.sonarr_api_url.rstrip("/")
        normalized_tv_folder = self.sonarr_tv_folder if self.sonarr_tv_folder.endswith("/") else f"{self.sonarr_tv_folder}/"

        object.__setattr__(self, "sonarr_api_url", normalized_api_url)
        object.__setattr__(self, "sonarr_tv_folder", normalized_tv_folder)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            download_folder=Path(os.getenv("DOWNLOAD_FOLDER", "/media/downloads")).expanduser(),
            tv_folder=Path(os.getenv("TV_FOLDER", "/media/tv")).expanduser(),
            movie_folder=Path(os.getenv("MOVIE_FOLDER", "/media/movies")).expanduser(),
            trash_folder=Path(os.getenv("TRASH_FOLDER", "/media/trash")).expanduser(),
            sonarr_api_url=os.getenv("SONARR_API_URL", "http://localhost:8989/api/v3"),
            sonarr_api_key=os.getenv("SONARR_API_KEY", ""),
            sonarr_tv_folder=os.getenv("SONARR_TV_FOLDER", "/media/tv/"),
            transmission_host=os.getenv("TRANSMISSION_HOST", "localhost"),
            transmission_port=cls._parse_int_env("TRANSMISSION_PORT", "9091"),
            transmission_user=os.getenv("TRANSMISSION_USER", ""),
            transmission_password=os.getenv("TRANSMISSION_PASSWORD", ""),
            sonarr_command_delay_seconds=cls._parse_float_env("SONARR_COMMAND_DELAY_SECONDS", "0"),
        )

    @staticmethod
    def _parse_int_env(name: str, default: str) -> int:
        value = os.getenv(name, default)
        try:
            return int(value)
        except ValueError as error:
            raise ValueError(f"Invalid value for {name}: {value!r} (expected integer)") from error

    @staticmethod
    def _parse_float_env(name: str, default: str) -> float:
        value = os.getenv(name, default)
        try:
            return float(value)
        except ValueError as error:
            raise ValueError(f"Invalid value for {name}: {value!r} (expected number)") from error
