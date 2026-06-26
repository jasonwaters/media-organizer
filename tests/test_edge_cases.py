from dataclasses import dataclass
from pathlib import Path

import pytest

from media_organizer.app import FileOrganizer, MediaOrganizer, SonarrService, TransmissionService, UnrarExtractor
from media_organizer.config import Settings


STOPPED = 0
DOWNLOADING = 4
SEEDING = 6


@dataclass
class TorrentWithBadProgress:
    name: str
    hashString: str | None = None
    progress: object = None
    hash_string: str | None = None
    percent_done: object = None
    is_finished: bool = False
    _status: int = SEEDING


class FakeTransmissionClient:
    def __init__(self, torrents):
        self._torrents = torrents
        self.removed = []

    def get_torrents(self):
        return self._torrents

    def remove_torrent(self, torrent_id: str, delete_data: bool = False):
        self.removed.append((torrent_id, delete_data))


class DummyExtractor:
    def __init__(self, fail_on_name: str | None = None):
        self.fail_on_name = fail_on_name

    def extract(self, archive_path: Path, destination: Path) -> None:
        if self.fail_on_name and archive_path.name == self.fail_on_name:
            raise RuntimeError("extract failed")


class FlakyHttp:
    def __init__(self, fail_path: str):
        self.fail_path = fail_path
        self.calls = []

    def post(self, url: str, *, headers: dict, json: dict, timeout: int):
        self.calls.append((url, headers, json, timeout))
        if json["path"] == self.fail_path:
            raise OSError("sonarr failure")

        class Response:
            status_code = 200

        return Response()


def test_transmission_skips_torrent_without_status_attribute():
    @dataclass
    class TorrentNoStatus:
        name: str
        hashString: str | None = None
        progress: float | None = None
        hash_string: str | None = None
        percent_done: float | None = None

    client = FakeTransmissionClient(
        [TorrentNoStatus(name="mystery", hashString="xyz", progress=100)]
    )
    service = TransmissionService(client_factory=lambda: client, transmission_error_type=RuntimeError)

    service.remove_finished_torrents()

    assert client.removed == []


def test_transmission_ignores_non_numeric_progress_values():
    client = FakeTransmissionClient(
        [
            TorrentWithBadProgress(name="bad", hashString="a", progress="not-a-number", _status=SEEDING),
            TorrentWithBadProgress(name="good", hashString="b", progress=100, _status=SEEDING),
        ]
    )
    service = TransmissionService(client_factory=lambda: client, transmission_error_type=RuntimeError)

    service.remove_finished_torrents()

    assert client.removed == [("b", False)]


def test_transmission_requires_both_complete_progress_and_done_status():
    client = FakeTransmissionClient(
        [
            TorrentWithBadProgress(name="no-progress-info", hashString="flag-id", _status=SEEDING),
            TorrentWithBadProgress(name="low-progress", hashString="other", progress=1, _status=SEEDING),
            TorrentWithBadProgress(name="complete", hashString="done", progress=100, _status=SEEDING),
        ]
    )
    service = TransmissionService(client_factory=lambda: client, transmission_error_type=RuntimeError)

    service.remove_finished_torrents()

    assert client.removed == [("done", False)]


def test_transmission_skips_finished_torrent_without_id():
    client = FakeTransmissionClient(
        [
            TorrentWithBadProgress(name="missing-id", progress=100, _status=SEEDING),
            TorrentWithBadProgress(name="normal", hashString="ok", progress=100, _status=SEEDING),
        ]
    )
    service = TransmissionService(client_factory=lambda: client, transmission_error_type=RuntimeError)

    service.remove_finished_torrents()

    assert client.removed == [("ok", False)]


def test_sonarr_continues_after_single_request_failure(settings):
    settings.tv_folder.mkdir(parents=True)
    (settings.tv_folder / "Show One").mkdir()
    (settings.tv_folder / "Show Two").mkdir()

    flaky_http = FlakyHttp(fail_path="/library/tv/Show One")
    service = SonarrService(settings=settings, http_client=flaky_http)

    service.scan_and_move_complete_tv_episodes()

    posted_paths = [call[2]["path"] for call in flaky_http.calls]
    assert posted_paths == ["/library/tv/Show One", "/library/tv/Show Two"]


def test_unrar_extractor_raises_when_binary_is_missing(monkeypatch):
    monkeypatch.setattr("media_organizer.app.shutil.which", lambda _: None)

    with pytest.raises(RuntimeError, match="not found in PATH"):
        UnrarExtractor(binary_name="unrar")


def test_unrar_extractor_calls_subprocess_with_expected_arguments(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("media_organizer.app.shutil.which", lambda _: "/usr/bin/unrar")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs

    monkeypatch.setattr("media_organizer.app.subprocess.run", fake_run)
    extractor = UnrarExtractor(binary_name="unrar")
    archive = tmp_path / "archive.rar"
    destination = tmp_path / "out"

    extractor.extract(archive, destination)

    assert captured["cmd"] == ["/usr/bin/unrar", "e", "-y", str(archive), str(destination)]
    assert captured["kwargs"]["check"] is True
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True


def test_file_organizer_continues_when_archive_extraction_fails(settings):
    settings.download_folder.mkdir(parents=True)

    bad_dir = settings.download_folder / "BadArchive"
    bad_dir.mkdir()
    (bad_dir / "bad.rar").write_text("broken")

    good_dir = settings.download_folder / "GoodShow"
    good_dir.mkdir()
    good_video = good_dir / "Good.Show.S01E01.mkv"
    good_video.write_bytes(b"x" * (settings.video_file_size_minimum + 1))

    organizer = FileOrganizer(settings=settings, extractor=DummyExtractor(fail_on_name="bad.rar"))
    organizer.process_downloads()

    assert (settings.tv_folder / good_video.name).exists()


def test_file_organizer_handles_missing_download_folder_without_error(settings):
    organizer = FileOrganizer(settings=settings, extractor=DummyExtractor())

    organizer.process_downloads()

    assert not settings.tv_folder.exists()
    assert not settings.movie_folder.exists()


def test_file_organizer_surfaces_non_os_errors(settings, monkeypatch):
    settings.download_folder.mkdir(parents=True)
    source_dir = settings.download_folder / "Shows"
    source_dir.mkdir()

    organizer = FileOrganizer(settings=settings, extractor=DummyExtractor())

    def raise_unexpected(_directory):
        raise RuntimeError("unexpected scanning failure")

    monkeypatch.setattr(organizer, "scan_for_videos", raise_unexpected)

    with pytest.raises(RuntimeError):
        organizer.process_downloads()


def test_file_organizer_continues_after_os_errors(settings, monkeypatch):
    settings.download_folder.mkdir(parents=True)
    first_dir = settings.download_folder / "first"
    second_dir = settings.download_folder / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    valid = second_dir / "Movie.2026.mp4"
    valid.write_bytes(b"x" * (settings.video_file_size_minimum + 1))

    organizer = FileOrganizer(settings=settings, extractor=DummyExtractor())
    original_scan_for_videos = organizer.scan_for_videos

    def flaky_scan(directory: Path):
        if directory == first_dir:
            raise OSError("filesystem issue")
        original_scan_for_videos(directory)

    monkeypatch.setattr(organizer, "scan_for_videos", flaky_scan)

    organizer.process_downloads()

    assert (settings.movie_folder / valid.name).exists()


def test_file_organizer_continues_when_move_fails(settings, monkeypatch):
    settings.download_folder.mkdir(parents=True)

    source_dir = settings.download_folder / "Mixed"
    source_dir.mkdir()
    first = source_dir / "First.Show.S01E01.mkv"
    second = source_dir / "Second.Movie.2025.mp4"
    first.write_bytes(b"x" * (settings.video_file_size_minimum + 1))
    second.write_bytes(b"x" * (settings.video_file_size_minimum + 1))

    real_move = __import__("shutil").move
    state = {"failed_once": False}

    def flaky_move(src, dst):
        if src.endswith(first.name) and not state["failed_once"]:
            state["failed_once"] = True
            raise OSError("move failed")
        return real_move(src, dst)

    monkeypatch.setattr("media_organizer.app.shutil.move", flaky_move)

    organizer = FileOrganizer(settings=settings, extractor=DummyExtractor())
    organizer.process_downloads()

    assert (settings.movie_folder / second.name).exists()


def test_delete_rars_skips_download_root_directory(settings):
    settings.download_folder.mkdir(parents=True)
    root_rar = settings.download_folder / "root.rar"
    root_rar.write_text("keep me")

    organizer = FileOrganizer(settings=settings, extractor=DummyExtractor())
    organizer.delete_rars(settings.download_folder)

    assert root_rar.exists()


def test_trash_folder_skips_download_root_directory(settings):
    settings.download_folder.mkdir(parents=True)

    organizer = FileOrganizer(settings=settings, extractor=DummyExtractor())
    organizer.trash_folder(settings.download_folder)

    assert settings.download_folder.exists()
    assert not settings.trash_folder.exists()


def test_trash_folder_uses_unique_name_on_conflict(settings):
    settings.download_folder.mkdir(parents=True)
    first = settings.download_folder / "duplicate"
    second = settings.download_folder / "duplicate"
    first.mkdir()

    organizer = FileOrganizer(settings=settings, extractor=DummyExtractor())
    organizer.trash_folder(first)

    replacement = settings.download_folder / "duplicate"
    replacement.mkdir()
    organizer.trash_folder(replacement)

    duplicates = sorted(path.name for path in settings.trash_folder.iterdir())
    assert len(duplicates) == 2
    assert duplicates[0] == "duplicate"
    assert duplicates[1].startswith("duplicate-")


class FakeTransmissionService:
    def __init__(self):
        self.called = False

    def remove_finished_torrents(self):
        self.called = True


class FakeFileOrganizer:
    def __init__(self):
        self.called = False

    def process_downloads(self):
        self.called = True


class FakeSonarrService:
    def __init__(self):
        self.called = False

    def scan_and_move_complete_tv_episodes(self):
        self.called = True


def test_media_organizer_integration_orchestrates_all_steps():
    transmission = FakeTransmissionService()
    files = FakeFileOrganizer()
    sonarr = FakeSonarrService()

    app = MediaOrganizer(transmission_service=transmission, file_organizer=files, sonarr_service=sonarr)
    app.run()

    assert transmission.called
    assert files.called
    assert sonarr.called


def test_settings_from_env_rejects_invalid_port(monkeypatch):
    monkeypatch.setenv("TRANSMISSION_PORT", "banana")

    with pytest.raises(ValueError, match="Invalid value for TRANSMISSION_PORT"):
        Settings.from_env()


def test_settings_from_env_rejects_invalid_sonarr_delay(monkeypatch):
    monkeypatch.setenv("SONARR_COMMAND_DELAY_SECONDS", "fast")

    with pytest.raises(ValueError, match="Invalid value for SONARR_COMMAND_DELAY_SECONDS"):
        Settings.from_env()


def test_settings_normalizes_sonarr_tv_folder():
    settings = Settings(
        download_folder=Path("/d"),
        tv_folder=Path("/tv"),
        movie_folder=Path("/m"),
        trash_folder=Path("/trash"),
        sonarr_api_url="http://sonarr:8989/api/v3/",
        sonarr_api_key="x",
        sonarr_tv_folder="/library/tv",
        transmission_host="localhost",
        transmission_port=9091,
        transmission_user="",
        transmission_password="",
    )

    assert settings.sonarr_tv_folder == "/library/tv/"
    assert settings.sonarr_api_url == "http://sonarr:8989/api/v3"
