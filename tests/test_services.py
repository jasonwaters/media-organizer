from dataclasses import dataclass

import pytest
from requests import RequestException

from media_organizer.app import SonarrService, TransmissionService
from media_organizer.config import Settings


@dataclass
class Torrent:
    name: str
    hashString: str | None = None
    progress: float | None = None
    hash_string: str | None = None
    percent_done: float | None = None
    is_finished: bool = False


class FakeTransmissionClient:
    def __init__(self, torrents):
        self._torrents = torrents
        self.removed = []

    def get_torrents(self):
        return self._torrents

    def remove_torrent(self, torrent_id: str, delete_data: bool = False):
        self.removed.append((torrent_id, delete_data))


class FakeHttp:
    def __init__(self):
        self.calls = []

    def post(self, url: str, *, headers: dict, json: dict, timeout: int):
        self.calls.append((url, headers, json, timeout))

        class Response:
            status_code = 201

        return Response()


class TypeErrorHttp:
    def post(self, url: str, *, headers: dict, json: dict, timeout: int):
        raise TypeError("programming bug")


class FailingRequestHttp:
    def post(self, url: str, *, headers: dict, json: dict, timeout: int):
        raise RequestException("network problem")


def test_transmission_removes_only_complete_torrents():
    client = FakeTransmissionClient(
        torrents=[
            Torrent(name="complete", hashString="aaa", progress=100),
            Torrent(name="partial", hashString="bbb", progress=99.5),
        ]
    )
    service = TransmissionService(client_factory=lambda: client, transmission_error_type=RuntimeError)

    service.remove_finished_torrents()

    assert client.removed == [("aaa", False)]


def test_transmission_supports_percent_done_and_hash_string():
    client = FakeTransmissionClient(
        torrents=[
            Torrent(name="done", hash_string="ccc", percent_done=1.0),
            Torrent(name="not_done", hash_string="ddd", percent_done=0.4),
        ]
    )
    service = TransmissionService(client_factory=lambda: client, transmission_error_type=RuntimeError)

    service.remove_finished_torrents()

    assert client.removed == [("ccc", False)]


def test_transmission_handles_connection_errors():
    service = TransmissionService(
        client_factory=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        transmission_error_type=RuntimeError,
    )

    service.remove_finished_torrents()


def test_sonarr_service_posts_commands_for_visible_tv_paths(settings):
    settings.tv_folder.mkdir(parents=True)
    (settings.tv_folder / "Show One").mkdir()
    (settings.tv_folder / ".hidden").mkdir()
    (settings.tv_folder / "@eaDir").mkdir()

    http = FakeHttp()
    service = SonarrService(settings=settings, http_client=http)

    service.scan_and_move_complete_tv_episodes()

    assert len(http.calls) == 1
    url, headers, payload, timeout = http.calls[0]
    assert url == "http://sonarr:8989/api/v3/command"
    assert headers["X-Api-Key"] == "key123"
    assert payload == {
        "name": "downloadedepisodesscan",
        "path": "/library/tv/Show One",
        "importMode": "Move",
    }
    assert timeout == 30


def test_sonarr_service_skips_when_tv_folder_missing(settings):
    http = FakeHttp()
    service = SonarrService(settings=settings, http_client=http)

    service.scan_and_move_complete_tv_episodes()

    assert http.calls == []


def test_sonarr_service_delays_between_commands(settings, monkeypatch):
    adjusted = Settings(**{**settings.__dict__, "sonarr_command_delay_seconds": 1.5})
    adjusted.tv_folder.mkdir(parents=True)
    (adjusted.tv_folder / "Show One").mkdir()
    (adjusted.tv_folder / "Show Two").mkdir()
    sleeps = []

    monkeypatch.setattr("media_organizer.app.sleep", lambda seconds: sleeps.append(seconds))
    service = SonarrService(settings=adjusted, http_client=FakeHttp())

    service.scan_and_move_complete_tv_episodes()

    assert sleeps == [1.5]


def test_sonarr_service_surfaces_programming_errors(settings):
    settings.tv_folder.mkdir(parents=True)
    (settings.tv_folder / "Show One").mkdir()
    service = SonarrService(settings=settings, http_client=TypeErrorHttp())

    with pytest.raises(TypeError):
        service.scan_and_move_complete_tv_episodes()


def test_sonarr_service_handles_request_errors(settings):
    settings.tv_folder.mkdir(parents=True)
    (settings.tv_folder / "Show One").mkdir()
    service = SonarrService(settings=settings, http_client=FailingRequestHttp())

    service.scan_and_move_complete_tv_episodes()
