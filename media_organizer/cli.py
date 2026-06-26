from __future__ import annotations

import logging
import shutil
import sys

import requests

from .app import FileOrganizer, MediaOrganizer, NszDecompressor, SonarrService, SwitchGameOrganizer, TransmissionService
from .config import Settings

logger = logging.getLogger(__name__)


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


def _build_switch_organizer(settings: Settings) -> SwitchGameOrganizer | None:
    if not settings.switch_folder:
        return None

    try:
        decompressor = NszDecompressor()
    except RuntimeError:
        logger.warning("nsz not found in PATH; .nsz decompression disabled")
        decompressor = None

    return SwitchGameOrganizer(settings=settings, decompressor=decompressor)


def build_app(settings: Settings | None = None, http_client=None) -> MediaOrganizer:
    settings = settings or Settings.from_env()
    transmission_service = _build_transmission_service(settings)
    file_organizer = FileOrganizer(settings=settings)
    sonarr_http_client = http_client or requests.Session()
    sonarr_service = SonarrService(settings=settings, http_client=sonarr_http_client)
    switch_organizer = _build_switch_organizer(settings)
    return MediaOrganizer(transmission_service, file_organizer, sonarr_service, switch_organizer)


def check() -> None:
    """Verify runtime dependencies are available. Exits non-zero on failure."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    errors: list[str] = []

    _check_python_imports(errors)
    _check_binary("unrar", required=True, errors=errors)
    _check_binary("nsz", required=False, errors=errors)

    if errors:
        for error in errors:
            logger.error("FAIL: %s", error)
        sys.exit(1)

    logger.info("All checks passed.")


def _check_python_imports(errors: list[str]) -> None:
    required_modules = [
        ("transmission_rpc", "transmission-rpc"),
        ("requests", "requests"),
    ]
    for module_name, package_name in required_modules:
        try:
            __import__(module_name)
            logger.info("OK: python package '%s'", package_name)
        except ImportError:
            errors.append(f"python package '{package_name}' not importable")

    try:
        from importlib.metadata import distribution
        distribution("nsz")
        logger.info("OK: python package 'nsz'")
    except Exception:
        logger.warning("WARN: python package 'nsz' not installed (optional)")


def _check_binary(name: str, *, required: bool, errors: list[str]) -> None:
    path = shutil.which(name)
    if path:
        logger.info("OK: binary '%s' found at %s", name, path)
    elif required:
        errors.append(f"binary '{name}' not found in PATH")
    else:
        logger.warning("WARN: binary '%s' not found in PATH (optional)", name)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s (%(asctime)s)")

    if "--check" in sys.argv:
        check()
        return

    app = build_app()
    app.run()


if __name__ == "__main__":
    main()
