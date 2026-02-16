import requests

from media_organizer import cli


class FakeTransmissionService:
    def remove_finished_torrents(self):
        return None


class FakeHttpClient:
    def post(self, url: str, *, headers: dict, json: dict, timeout: int):
        return None


def test_build_app_uses_injected_http_client(settings, monkeypatch):
    monkeypatch.setattr(cli, "_build_transmission_service", lambda _settings: FakeTransmissionService())
    injected = FakeHttpClient()

    app = cli.build_app(settings=settings, http_client=injected)

    assert app.sonarr_service.http_client is injected


def test_build_app_creates_session_by_default(settings, monkeypatch):
    monkeypatch.setattr(cli, "_build_transmission_service", lambda _settings: FakeTransmissionService())

    app = cli.build_app(settings=settings)

    assert isinstance(app.sonarr_service.http_client, requests.Session)
