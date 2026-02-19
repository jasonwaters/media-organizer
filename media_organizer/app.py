from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Callable, Protocol

from requests import RequestException

from .config import Settings

logger = logging.getLogger(__name__)
SONARR_COMMAND_ENDPOINT = "/command"
SONARR_COMMAND_TIMEOUT_SECONDS = 30


class ArchiveExtractor(Protocol):
    def extract(self, archive_path: Path, destination: Path) -> None:
        ...


class TorrentInfo(Protocol):
    """Expected torrent attributes from transmission client objects.

    We support both attribute conventions (`hashString`/`progress` and
    `hash_string`/`percent_done`) for compatibility with mixed environments and
    historical client behavior.
    """

    name: str
    hashString: str | None
    hash_string: str | None
    progress: float | None
    percent_done: float | None


class TransmissionClient(Protocol):
    def get_torrents(self) -> Iterable[TorrentInfo]:
        ...

    def remove_torrent(self, torrent_id: str, delete_data: bool = False) -> None:
        ...


class HttpClient(Protocol):
    def post(self, url: str, *, headers: dict, json: dict, timeout: int):
        ...


@dataclass(frozen=True)
class FlagFile:
    remove_folder: str = ".removefolder"
    unrared: str = ".unrared"


class UnrarExtractor:
    def __init__(self, binary_name: str = "unrar") -> None:
        self.binary_name = binary_name
        self.binary_path = shutil.which(binary_name)
        if not self.binary_path:
            raise RuntimeError(f"{binary_name} not found in PATH")

    def extract(self, archive_path: Path, destination: Path) -> None:
        subprocess.run(
            [self.binary_path, "e", "-y", str(archive_path), str(destination)],
            check=True,
            capture_output=True,
            text=True,
        )


class TransmissionService:
    def __init__(self, client_factory: Callable[[], TransmissionClient], transmission_error_type: type[Exception]) -> None:
        self._client_factory = client_factory
        self._transmission_error_type = transmission_error_type

    def remove_finished_torrents(self) -> None:
        try:
            client = self._client_factory()
            for torrent in self._iter_finished_torrents(client.get_torrents()):
                self._remove_torrent(client, torrent)
        except self._transmission_error_type:
            logger.exception("Unable to connect to Transmission")

    def _iter_finished_torrents(self, torrents: Iterable[object]) -> Iterable[object]:
        for torrent in torrents:
            if self._is_finished(torrent):
                yield torrent

    def _remove_torrent(self, client: TransmissionClient, torrent: object) -> None:
        torrent_name = getattr(torrent, "name", "<unknown>")
        torrent_id = self._get_torrent_id(torrent)
        if not torrent_id:
            logger.warning("Skipping finished torrent with no id: %s", torrent_name)
            return

        logger.info("Removed '%s'", torrent_name)
        client.remove_torrent(torrent_id, delete_data=False)

    @staticmethod
    def _get_torrent_id(torrent: object) -> str | None:
        return getattr(torrent, "hashString", None) or getattr(torrent, "hash_string", None)

    # Transmission status codes where downloading/processing is still in progress
    _INCOMPLETE_STATUSES = frozenset({
        1,  # check pending
        2,  # checking
        3,  # download pending
        4,  # downloading
    })

    @staticmethod
    def _is_finished(torrent: object) -> bool:
        if TransmissionService._is_still_processing(torrent):
            return False

        return TransmissionService._is_download_complete(torrent)

    @staticmethod
    def _is_still_processing(torrent: object) -> bool:
        status = getattr(torrent, "_status", None) if hasattr(torrent, "_status") else getattr(torrent, "status", None)
        if isinstance(status, int):
            return status in TransmissionService._INCOMPLETE_STATUSES
        return False

    @staticmethod
    def _is_download_complete(torrent: object) -> bool:
        progress = TransmissionService._as_float(getattr(torrent, "progress", None))
        if progress is not None:
            return progress >= 100

        percent_done = TransmissionService._as_float(getattr(torrent, "percent_done", None))
        if percent_done is not None:
            return percent_done >= 1.0

        return False

    @staticmethod
    def _as_float(value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class SonarrService:
    def __init__(self, settings: Settings, http_client: HttpClient) -> None:
        self.settings = settings
        self.http_client = http_client

    def scan_and_move_complete_tv_episodes(self) -> None:
        if not self.settings.tv_folder.exists():
            logger.warning("TV folder does not exist: %s", self.settings.tv_folder)
            return

        headers = self._build_headers()
        items = list(self._iter_visible_items())
        for index, item in enumerate(items):
            item_path = self._to_sonarr_path(item.name)
            payload = self._build_payload(item_path)
            self._notify_sonarr(item_path, headers, payload)
            self._sleep_between_commands(index, len(items))

    def _build_headers(self) -> dict[str, str]:
        return {
            "accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": self.settings.sonarr_api_key,
        }

    def _iter_visible_items(self) -> Iterable[Path]:
        for item in sorted(self.settings.tv_folder.iterdir()):
            name = item.name
            if name.startswith(".") or name.startswith("@"):
                continue
            yield item

    def _to_sonarr_path(self, name: str) -> str:
        return f"{self.settings.sonarr_tv_folder.rstrip('/')}/{name}"

    @staticmethod
    def _build_payload(item_path: str) -> dict[str, str]:
        return {
            "name": "downloadedepisodesscan",
            "path": item_path,
            "importMode": "Move",
        }

    def _notify_sonarr(self, item_path: str, headers: dict[str, str], payload: dict[str, str]) -> None:
        try:
            response = self.http_client.post(
                f"{self.settings.sonarr_api_url}{SONARR_COMMAND_ENDPOINT}",
                headers=headers,
                json=payload,
                timeout=SONARR_COMMAND_TIMEOUT_SECONDS,
            )
            logger.info("Asked Sonarr to rename/import [%s, %s]", item_path, getattr(response, "status_code", "n/a"))
        except (RequestException, OSError):
            logger.exception("Failed to notify Sonarr for %s", item_path)

    def _sleep_between_commands(self, index: int, total_items: int) -> None:
        delay = self.settings.sonarr_command_delay_seconds
        if delay <= 0:
            return

        has_next_item = index < total_items - 1
        if has_next_item:
            sleep(delay)


class FileOrganizer:
    PATTERN_EPISODE = re.compile(r".*(((s\d{1,2}e\d{1,2})|(\d+x\d+))|(\.\d{3}\.)|(\d{4}\.\d{2}\.\d{2})).*", re.IGNORECASE)
    PATTERN_VIDEO = re.compile(r"^.+\.(avi|mp4|mkv)$", re.IGNORECASE)
    PATTERN_TORRENT_PART = re.compile(r"^.+\.part$", re.IGNORECASE)
    PATTERN_RAR = re.compile(r"^.+\.(rar|r\d+)$", re.IGNORECASE)

    SUPPORTED_ARCHIVE_EXTENSIONS = (".rar", ".r01")

    def __init__(self, settings: Settings, extractor: ArchiveExtractor | None = None, flag_file: FlagFile | None = None):
        self.settings = settings
        self.extractor = extractor or UnrarExtractor()
        self.flag_file = flag_file or FlagFile()

    def process_downloads(self) -> None:
        if not self.settings.download_folder.exists():
            logger.warning("Download folder does not exist: %s", self.settings.download_folder)
            return

        for dirname, _, _ in os.walk(self.settings.download_folder):
            directory = Path(dirname)
            self._process_directory(directory)

    def _process_directory(self, directory: Path) -> None:
        try:
            self.scan_for_archives(directory)
            self.scan_for_videos(directory)
            self.clean_up(directory)
        except OSError:
            logger.exception("Failed to process directory: %s", directory)

    def scan_for_archives(self, directory: Path) -> None:
        for item in sorted(directory.iterdir()):
            if item.suffix.lower() in self.SUPPORTED_ARCHIVE_EXTENSIONS:
                if not (directory / self.flag_file.unrared).exists():
                    logger.info("Need to extract: %s", item.name)
                    self._extract_archive(directory, item.name)
                break

    def _extract_archive(self, directory: Path, archive_name: str) -> None:
        try:
            self.start_unrar(directory, archive_name)
        except Exception:
            logger.exception("Failed to extract archive: %s", directory / archive_name)

    def scan_for_videos(self, directory: Path) -> None:
        for item in sorted(directory.iterdir()):
            self._move_video_if_eligible(directory, item)

        if self._directory_contains_torrent_part(directory):
            self.clear_mark(directory, self.flag_file.remove_folder)

    def _move_video_if_eligible(self, directory: Path, item: Path) -> None:
        if not item.is_file() or not self.is_valid_video_file(item.name):
            return

        if item.stat().st_size <= self.settings.video_file_size_minimum:
            return

        destination = self._destination_for_video(item.name)
        logger.info("Moving %s", item.name)
        try:
            destination.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item), str(destination))
            self.create_mark(directory, self.flag_file.remove_folder)
            logger.info("Moved %s", item.name)
        except OSError:
            logger.exception("Failed to move file: %s", item)

    def _destination_for_video(self, name: str) -> Path:
        if self.is_tv_episode(name):
            return self.settings.tv_folder
        return self.settings.movie_folder

    def _directory_contains_torrent_part(self, directory: Path) -> bool:
        return any(self.is_torrent_part(item.name) for item in directory.iterdir())

    def clean_up(self, directory: Path) -> None:
        unrared = (directory / self.flag_file.unrared).exists()
        remove_folder = (directory / self.flag_file.remove_folder).exists()

        if unrared:
            self.delete_rars(directory)

        if remove_folder:
            self.trash_folder(directory)

    def delete_rars(self, directory: Path) -> None:
        if directory == self.settings.download_folder:
            return

        for item in directory.iterdir():
            if item.is_file() and self.is_rar(item.name):
                logger.info("Deleting archive %s", item.name)
                item.unlink(missing_ok=True)

    def start_unrar(self, directory: Path, archive_name: str) -> None:
        archive_path = directory / archive_name
        self.extractor.extract(archive_path, directory)
        self.create_mark(directory, self.flag_file.unrared)
        self.delete_rars(directory)

    def create_mark(self, directory: Path, mark_file_name: str) -> None:
        mark_file = directory / mark_file_name
        mark_file.touch(exist_ok=True)

    def clear_mark(self, directory: Path, mark_file_name: str) -> None:
        mark_file = directory / mark_file_name
        mark_file.unlink(missing_ok=True)

    def trash_folder(self, directory: Path) -> None:
        if directory == self.settings.download_folder:
            return

        logger.info("Deleting folder %s", directory)
        self.settings.trash_folder.mkdir(parents=True, exist_ok=True)
        destination = self._resolve_trash_destination(directory.name)
        shutil.move(str(directory), str(destination))

    def _resolve_trash_destination(self, directory_name: str) -> Path:
        destination = self.settings.trash_folder / directory_name
        if not destination.exists():
            return destination

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        sequence = 1
        while True:
            candidate = self.settings.trash_folder / f"{directory_name}-{timestamp}-{sequence}"
            if not candidate.exists():
                return candidate
            sequence += 1

    @classmethod
    def is_rar(cls, name: str) -> bool:
        return cls.PATTERN_RAR.match(name) is not None

    @classmethod
    def is_tv_episode(cls, name: str) -> bool:
        return cls.PATTERN_EPISODE.match(name) is not None

    @classmethod
    def is_valid_video_file(cls, name: str) -> bool:
        return cls.PATTERN_VIDEO.match(name) is not None and "sample" not in name.lower()

    @classmethod
    def is_torrent_part(cls, name: str) -> bool:
        return cls.PATTERN_TORRENT_PART.match(name) is not None


class MediaOrganizer:
    def __init__(self, transmission_service: TransmissionService, file_organizer: FileOrganizer, sonarr_service: SonarrService):
        self.transmission_service = transmission_service
        self.file_organizer = file_organizer
        self.sonarr_service = sonarr_service

    def run(self) -> None:
        self.transmission_service.remove_finished_torrents()
        self.file_organizer.process_downloads()
        self.sonarr_service.scan_and_move_complete_tv_episodes()
