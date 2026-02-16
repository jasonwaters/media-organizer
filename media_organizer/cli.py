from __future__ import annotations

import logging

import requests

from .app import FileOrganizer, MediaOrganizer, SonarrService, TransmissionService
from .config import Settings


def _build_transmission_service(settings: Settings) -> TransmissionService:
    try:
        import transmission_rpc
        from transmission_rpc.error import TransmissionError
    except ImportError as exc:
        raise RuntimeError("Missing dependency 'transmission-rpc'. Install requirements first.") from exc

    def factory():
        return transmission_rpc.Client(
            host=settings.transmission_host,
            port=settings.transmission_port,
            username=settings.transmission_user or None,
            password=settings.transmission_password or None,
        )

    return TransmissionService(client_factory=factory, transmission_error_type=TransmissionError)


def build_app(settings: Settings | None = None, http_client=None) -> MediaOrganizer:
    settings = settings or Settings.from_env()
    transmission_service = _build_transmission_service(settings)
    file_organizer = FileOrganizer(settings=settings)
    sonarr_http_client = http_client or requests.Session()
    sonarr_service = SonarrService(settings=settings, http_client=sonarr_http_client)
    return MediaOrganizer(transmission_service, file_organizer, sonarr_service)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s (%(asctime)s)")
    app = build_app()
    app.run()


if __name__ == "__main__":
    main()
