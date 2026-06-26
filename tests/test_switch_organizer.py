import shutil
from pathlib import Path

import pytest

from media_organizer.app import NszDecompressor, SwitchGameOrganizer
from media_organizer.config import Settings


@pytest.fixture
def switch_settings(tmp_path: Path) -> Settings:
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
        switch_folder=tmp_path / "switch",
    )


@pytest.fixture
def no_switch_settings(tmp_path: Path) -> Settings:
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
        switch_folder=None,
    )


class TestSwitchFileClassification:
    def test_nsp_is_switch_file(self):
        assert SwitchGameOrganizer._is_switch_file("Game Title [0100ABC].nsp")

    def test_nsz_is_switch_file(self):
        assert SwitchGameOrganizer._is_switch_file("Game.nsz")

    def test_xci_is_switch_file(self):
        assert SwitchGameOrganizer._is_switch_file("dump.xci")

    def test_case_insensitive(self):
        assert SwitchGameOrganizer._is_switch_file("GAME.NSP")
        assert SwitchGameOrganizer._is_switch_file("Game.XCI")
        assert SwitchGameOrganizer._is_switch_file("title.NSZ")

    def test_mkv_is_not_switch_file(self):
        assert not SwitchGameOrganizer._is_switch_file("Show.S01E01.mkv")

    def test_rar_is_not_switch_file(self):
        assert not SwitchGameOrganizer._is_switch_file("archive.rar")

    def test_no_extension_is_not_switch_file(self):
        assert not SwitchGameOrganizer._is_switch_file("README")


class TestDirectoryClassification:
    def test_directory_with_nsp_is_switch(self, tmp_path):
        game_dir = tmp_path / "MyGame"
        game_dir.mkdir()
        (game_dir / "game.nsp").write_bytes(b"data")
        (game_dir / "readme.txt").write_bytes(b"info")

        assert SwitchGameOrganizer._directory_contains_switch_files(game_dir)

    def test_directory_with_only_video_is_not_switch(self, tmp_path):
        media_dir = tmp_path / "Show"
        media_dir.mkdir()
        (media_dir / "episode.mkv").write_bytes(b"video")

        assert not SwitchGameOrganizer._directory_contains_switch_files(media_dir)

    def test_empty_directory_is_not_switch(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        assert not SwitchGameOrganizer._directory_contains_switch_files(empty_dir)

    def test_nonexistent_directory_is_not_switch(self, tmp_path):
        assert not SwitchGameOrganizer._directory_contains_switch_files(tmp_path / "nope")


class TestSwitchMoveFiles:
    def test_moves_loose_nsp_file(self, switch_settings):
        switch_settings.download_folder.mkdir(parents=True)
        nsp = switch_settings.download_folder / "Game [ABC123].nsp"
        nsp.write_bytes(b"nsp-data")

        organizer = SwitchGameOrganizer(settings=switch_settings)
        organizer.process_downloads()

        assert (switch_settings.switch_folder / nsp.name).exists()
        assert not nsp.exists()

    def test_moves_directory_containing_switch_files(self, switch_settings):
        switch_settings.download_folder.mkdir(parents=True)
        game_dir = switch_settings.download_folder / "MyGame"
        game_dir.mkdir()
        (game_dir / "base.nsp").write_bytes(b"base")
        (game_dir / "update.nsp").write_bytes(b"update")

        organizer = SwitchGameOrganizer(settings=switch_settings)
        organizer.process_downloads()

        dest_dir = switch_settings.switch_folder / "MyGame"
        assert dest_dir.exists()
        assert (dest_dir / "base.nsp").exists()
        assert (dest_dir / "update.nsp").exists()
        assert not game_dir.exists()

    def test_leaves_video_directories_alone(self, switch_settings):
        switch_settings.download_folder.mkdir(parents=True)
        media_dir = switch_settings.download_folder / "Show.S01E01"
        media_dir.mkdir()
        (media_dir / "Show.S01E01.mkv").write_bytes(b"video")

        organizer = SwitchGameOrganizer(settings=switch_settings)
        organizer.process_downloads()

        assert media_dir.exists()
        assert not (switch_settings.switch_folder / "Show.S01E01").exists()

    def test_skips_hidden_directories(self, switch_settings):
        switch_settings.download_folder.mkdir(parents=True)
        hidden = switch_settings.download_folder / ".hidden_game"
        hidden.mkdir()
        (hidden / "game.nsp").write_bytes(b"data")

        organizer = SwitchGameOrganizer(settings=switch_settings)
        organizer.process_downloads()

        assert hidden.exists()

    def test_skips_synology_metadata_directories(self, switch_settings):
        switch_settings.download_folder.mkdir(parents=True)
        ea_dir = switch_settings.download_folder / "@eaDir"
        ea_dir.mkdir()
        (ea_dir / "something.nsp").write_bytes(b"data")

        organizer = SwitchGameOrganizer(settings=switch_settings)
        organizer.process_downloads()

        assert ea_dir.exists()


class TestSwitchMerge:
    def test_merges_into_existing_destination(self, switch_settings):
        switch_settings.download_folder.mkdir(parents=True)
        switch_settings.switch_folder.mkdir(parents=True)

        game_dir = switch_settings.download_folder / "MyGame"
        game_dir.mkdir()
        (game_dir / "update.nsp").write_bytes(b"new-update")

        dest_dir = switch_settings.switch_folder / "MyGame"
        dest_dir.mkdir()
        (dest_dir / "base.nsp").write_bytes(b"existing-base")

        organizer = SwitchGameOrganizer(settings=switch_settings)
        organizer.process_downloads()

        assert (dest_dir / "base.nsp").read_bytes() == b"existing-base"
        assert (dest_dir / "update.nsp").read_bytes() == b"new-update"
        assert not game_dir.exists()

    def test_merge_updates_newer_files(self, switch_settings):
        import time

        switch_settings.download_folder.mkdir(parents=True)
        switch_settings.switch_folder.mkdir(parents=True)

        dest_dir = switch_settings.switch_folder / "MyGame"
        dest_dir.mkdir()
        old_file = dest_dir / "game.nsp"
        old_file.write_bytes(b"old-version")

        time.sleep(0.05)

        game_dir = switch_settings.download_folder / "MyGame"
        game_dir.mkdir()
        new_file = game_dir / "game.nsp"
        new_file.write_bytes(b"new-version")

        organizer = SwitchGameOrganizer(settings=switch_settings)
        organizer.process_downloads()

        assert old_file.read_bytes() == b"new-version"

    def test_merge_preserves_newer_destination_file(self, switch_settings):
        import time

        switch_settings.download_folder.mkdir(parents=True)
        switch_settings.switch_folder.mkdir(parents=True)

        game_dir = switch_settings.download_folder / "MyGame"
        game_dir.mkdir()
        source_file = game_dir / "game.nsp"
        source_file.write_bytes(b"old-source")

        time.sleep(0.05)

        dest_dir = switch_settings.switch_folder / "MyGame"
        dest_dir.mkdir()
        dest_file = dest_dir / "game.nsp"
        dest_file.write_bytes(b"newer-dest")

        organizer = SwitchGameOrganizer(settings=switch_settings)
        organizer.process_downloads()

        assert dest_file.read_bytes() == b"newer-dest"


class TestSwitchDisabled:
    def test_does_nothing_when_switch_folder_not_configured(self, no_switch_settings):
        no_switch_settings.download_folder.mkdir(parents=True)
        game_dir = no_switch_settings.download_folder / "MyGame"
        game_dir.mkdir()
        (game_dir / "game.nsp").write_bytes(b"data")

        organizer = SwitchGameOrganizer(settings=no_switch_settings)
        organizer.process_downloads()

        assert game_dir.exists()

    def test_does_nothing_when_download_folder_missing(self, switch_settings):
        organizer = SwitchGameOrganizer(settings=switch_settings)
        organizer.process_downloads()


class TestSwitchResilience:
    def test_continues_after_move_failure(self, switch_settings, monkeypatch):
        switch_settings.download_folder.mkdir(parents=True)

        first = switch_settings.download_folder / "GameA"
        first.mkdir()
        (first / "a.nsp").write_bytes(b"a")

        second = switch_settings.download_folder / "GameB"
        second.mkdir()
        (second / "b.nsp").write_bytes(b"b")

        real_move = shutil.move
        state = {"failed": False}

        def flaky_move(src, dst):
            if "GameA" in str(src) and not state["failed"]:
                state["failed"] = True
                raise OSError("permission denied")
            return real_move(src, dst)

        monkeypatch.setattr("media_organizer.app.shutil.move", flaky_move)

        organizer = SwitchGameOrganizer(settings=switch_settings)
        organizer.process_downloads()

        assert (switch_settings.switch_folder / "GameB").exists()
        assert first.exists()


class TestRaceConditionPrevention:
    """The key bug fix: switch files are moved BEFORE video processing,
    so the FileOrganizer never sees them."""

    def test_switch_runs_before_file_organizer(self, tmp_path):
        from media_organizer.app import FileOrganizer, MediaOrganizer, SwitchGameOrganizer, TransmissionService

        settings = Settings(
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
            switch_folder=tmp_path / "switch",
        )

        settings.download_folder.mkdir(parents=True)

        game_dir = settings.download_folder / "MyGame"
        game_dir.mkdir()
        (game_dir / "base.nsp").write_bytes(b"nsp")
        (game_dir / "video.mkv").write_bytes(b"x" * 20_000_000)

        class FakeTransmissionService:
            def remove_finished_torrents(self):
                pass

        class FakeHttp:
            def post(self, *args, **kwargs):
                class R:
                    status_code = 200
                return R()

        from media_organizer.app import SonarrService

        class DummyExtractor:
            def extract(self, archive_path, destination):
                pass

        transmission = FakeTransmissionService()
        file_organizer = FileOrganizer(settings=settings, extractor=DummyExtractor())
        sonarr = SonarrService(settings=settings, http_client=FakeHttp())
        switch_organizer = SwitchGameOrganizer(settings=settings)

        app = MediaOrganizer(
            transmission_service=transmission,
            file_organizer=file_organizer,
            sonarr_service=sonarr,
            switch_organizer=switch_organizer,
        )
        app.run()

        assert (settings.switch_folder / "MyGame" / "base.nsp").exists()
        assert (settings.switch_folder / "MyGame" / "video.mkv").exists()
        assert not (settings.movie_folder / "video.mkv").exists()
        assert not (settings.tv_folder / "video.mkv").exists()


class FakeDecompressor:
    """Simulates nsz decompression by renaming .nsz to .nsp."""

    def __init__(self, fail_for: set[str] | None = None):
        self.calls: list[Path] = []
        self._fail_for = fail_for or set()

    def decompress(self, nsz_path: Path) -> Path | None:
        self.calls.append(nsz_path)
        if nsz_path.name in self._fail_for:
            return None
        nsp_path = nsz_path.with_suffix(".nsp")
        nsz_path.rename(nsp_path)
        return nsp_path


class TestNszDecompression:
    def test_decompresses_loose_nsz_file_before_moving(self, switch_settings):
        switch_settings.download_folder.mkdir(parents=True)
        nsz = switch_settings.download_folder / "Game.nsz"
        nsz.write_bytes(b"compressed")

        decompressor = FakeDecompressor()
        organizer = SwitchGameOrganizer(settings=switch_settings, decompressor=decompressor)
        organizer.process_downloads()

        assert (switch_settings.switch_folder / "Game.nsp").exists()
        assert not (switch_settings.switch_folder / "Game.nsz").exists()
        assert len(decompressor.calls) == 1

    def test_decompresses_nsz_in_directory_before_moving(self, switch_settings):
        switch_settings.download_folder.mkdir(parents=True)
        game_dir = switch_settings.download_folder / "MyGame"
        game_dir.mkdir()
        (game_dir / "base.nsz").write_bytes(b"compressed-base")
        (game_dir / "update.nsp").write_bytes(b"already-nsp")

        decompressor = FakeDecompressor()
        organizer = SwitchGameOrganizer(settings=switch_settings, decompressor=decompressor)
        organizer.process_downloads()

        dest = switch_settings.switch_folder / "MyGame"
        assert (dest / "base.nsp").exists()
        assert (dest / "update.nsp").exists()
        assert not (dest / "base.nsz").exists()
        assert len(decompressor.calls) == 1

    def test_moves_nsz_as_is_when_decompression_fails(self, switch_settings):
        switch_settings.download_folder.mkdir(parents=True)
        nsz = switch_settings.download_folder / "Broken.nsz"
        nsz.write_bytes(b"bad-data")

        decompressor = FakeDecompressor(fail_for={"Broken.nsz"})
        organizer = SwitchGameOrganizer(settings=switch_settings, decompressor=decompressor)
        organizer.process_downloads()

        assert (switch_settings.switch_folder / "Broken.nsz").exists()

    def test_skips_decompression_when_no_decompressor(self, switch_settings):
        switch_settings.download_folder.mkdir(parents=True)
        nsz = switch_settings.download_folder / "Game.nsz"
        nsz.write_bytes(b"compressed")

        organizer = SwitchGameOrganizer(settings=switch_settings, decompressor=None)
        organizer.process_downloads()

        assert (switch_settings.switch_folder / "Game.nsz").exists()

    def test_skips_already_converted_nsp(self, switch_settings):
        switch_settings.download_folder.mkdir(parents=True)
        nsp = switch_settings.download_folder / "Game.nsp"
        nsp.write_bytes(b"already-decompressed")

        decompressor = FakeDecompressor()
        organizer = SwitchGameOrganizer(settings=switch_settings, decompressor=decompressor)
        organizer.process_downloads()

        assert (switch_settings.switch_folder / "Game.nsp").exists()
        assert len(decompressor.calls) == 0

    def test_directory_decompression_failure_does_not_block_move(self, switch_settings):
        switch_settings.download_folder.mkdir(parents=True)
        game_dir = switch_settings.download_folder / "MyGame"
        game_dir.mkdir()
        (game_dir / "bad.nsz").write_bytes(b"corrupt")
        (game_dir / "good.nsp").write_bytes(b"fine")

        decompressor = FakeDecompressor(fail_for={"bad.nsz"})
        organizer = SwitchGameOrganizer(settings=switch_settings, decompressor=decompressor)
        organizer.process_downloads()

        dest = switch_settings.switch_folder / "MyGame"
        assert (dest / "bad.nsz").exists()
        assert (dest / "good.nsp").exists()


class TestNszDecompressorUnit:
    def test_raises_when_binary_not_found(self, monkeypatch):
        monkeypatch.setattr("media_organizer.app.shutil.which", lambda _: None)

        with pytest.raises(RuntimeError, match="not found in PATH"):
            NszDecompressor()

    def test_calls_subprocess_with_expected_arguments(self, monkeypatch, tmp_path):
        monkeypatch.setattr("media_organizer.app.shutil.which", lambda _: "/usr/local/bin/nsz")
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs
            source = Path(cmd[-1])
            source.with_suffix(".nsp").write_bytes(b"decompressed")

            class Result:
                returncode = 0
                stderr = ""
            return Result()

        monkeypatch.setattr("media_organizer.app.subprocess.run", fake_run)
        decompressor = NszDecompressor()

        nsz_file = tmp_path / "game.nsz"
        nsz_file.write_bytes(b"compressed")
        result = decompressor.decompress(nsz_file)

        assert captured["cmd"] == ["/usr/local/bin/nsz", "-D", "--overwrite", str(nsz_file)]
        assert captured["kwargs"]["capture_output"] is True
        assert captured["kwargs"]["text"] is True
        assert result == tmp_path / "game.nsp"
        assert not nsz_file.exists(), "source .nsz should be removed after successful decompress"

    def test_returns_none_on_subprocess_failure(self, monkeypatch, tmp_path):
        monkeypatch.setattr("media_organizer.app.shutil.which", lambda _: "/usr/local/bin/nsz")

        def fake_run(cmd, **kwargs):
            class Result:
                returncode = 1
                stderr = "keys not found"
            return Result()

        monkeypatch.setattr("media_organizer.app.subprocess.run", fake_run)
        decompressor = NszDecompressor()

        nsz_file = tmp_path / "game.nsz"
        nsz_file.write_bytes(b"compressed")
        result = decompressor.decompress(nsz_file)

        assert result is None
        assert nsz_file.exists(), "source .nsz must be preserved when decompression fails"
