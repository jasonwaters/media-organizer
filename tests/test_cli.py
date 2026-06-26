import pytest
import requests

from media_organizer import cli


def test_check_passes_when_dependencies_available(monkeypatch):
    monkeypatch.setattr("media_organizer.cli.shutil.which", lambda name: f"/usr/bin/{name}")
    cli.check()


def test_check_exits_nonzero_when_required_binary_missing(monkeypatch):
    def selective_which(name):
        if name == "unrar":
            return None
        return f"/usr/bin/{name}"

    monkeypatch.setattr("media_organizer.cli.shutil.which", selective_which)

    with pytest.raises(SystemExit) as exc_info:
        cli.check()
    assert exc_info.value.code == 1


def test_check_passes_when_optional_nsz_missing(monkeypatch):
    def selective_which(name):
        if name == "nsz":
            return None
        return f"/usr/bin/{name}"

    monkeypatch.setattr("media_organizer.cli.shutil.which", selective_which)
    cli.check()


class FakeTransmissionService:
    def remove_finished_torrents(self):
        return None


class FakeFileOrganizer:
    def __init__(self, settings):
        self.settings = settings

    def process_downloads(self):
        return None


class FakeHttpClient:
    def post(self, url: str, *, headers: dict, json: dict, timeout: int):
        return None


def test_build_app_uses_injected_http_client(settings, monkeypatch):
    monkeypatch.setattr(cli, "_build_transmission_service", lambda _settings: FakeTransmissionService())
    monkeypatch.setattr(cli, "FileOrganizer", FakeFileOrganizer)
    injected = FakeHttpClient()

    app = cli.build_app(settings=settings, http_client=injected)

    assert app.sonarr_service.http_client is injected


def test_build_app_creates_session_by_default(settings, monkeypatch):
    monkeypatch.setattr(cli, "_build_transmission_service", lambda _settings: FakeTransmissionService())
    monkeypatch.setattr(cli, "FileOrganizer", FakeFileOrganizer)

    app = cli.build_app(settings=settings)

    assert isinstance(app.sonarr_service.http_client, requests.Session)
