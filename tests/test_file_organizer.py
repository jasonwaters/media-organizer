from pathlib import Path

from media_organizer.app import FileOrganizer


class DummyExtractor:
    def __init__(self):
        self.calls = []

    def extract(self, archive_path: Path, destination: Path) -> None:
        self.calls.append((archive_path, destination))


def test_moves_tv_and_movie_files(settings):
    settings.download_folder.mkdir(parents=True)
    show_dir = settings.download_folder / "Some.Show"
    show_dir.mkdir()

    tv_file = show_dir / "Some.Show.S01E02.mkv"
    movie_file = show_dir / "Some.Movie.2023.mp4"
    tv_file.write_bytes(b"x" * (settings.video_file_size_minimum + 1))
    movie_file.write_bytes(b"x" * (settings.video_file_size_minimum + 1))

    organizer = FileOrganizer(settings, extractor=DummyExtractor())
    organizer.process_downloads()

    assert (settings.tv_folder / tv_file.name).exists()
    assert (settings.movie_folder / movie_file.name).exists()
    assert (settings.trash_folder / show_dir.name).exists()


def test_does_not_remove_directory_with_part_file(settings):
    settings.download_folder.mkdir(parents=True)
    show_dir = settings.download_folder / "InProgress"
    show_dir.mkdir()

    episode = show_dir / "In.Progress.S01E01.mkv"
    episode.write_bytes(b"x" * (settings.video_file_size_minimum + 1))
    (show_dir / "In.Progress.part").write_text("still downloading")

    organizer = FileOrganizer(settings, extractor=DummyExtractor())
    organizer.process_downloads()

    assert (settings.tv_folder / episode.name).exists()
    assert show_dir.exists()


def test_extracts_rar_once_and_deletes_rars(settings):
    settings.download_folder.mkdir(parents=True)
    archive_dir = settings.download_folder / "Archive"
    archive_dir.mkdir()

    (archive_dir / "release.rar").write_text("rar")
    (archive_dir / "release.r01").write_text("r01")

    extractor = DummyExtractor()
    organizer = FileOrganizer(settings, extractor=extractor)
    organizer.process_downloads()

    assert len(extractor.calls) == 1
    assert not (archive_dir / "release.rar").exists()
    assert not (archive_dir / "release.r01").exists()
    assert (archive_dir / ".unrared").exists()


def test_ignores_small_video_files(settings):
    settings.download_folder.mkdir(parents=True)
    source_dir = settings.download_folder / "Small"
    source_dir.mkdir()

    tiny_file = source_dir / "Tiny.Movie.mp4"
    tiny_file.write_bytes(b"x" * (settings.video_file_size_minimum - 1))

    organizer = FileOrganizer(settings, extractor=DummyExtractor())
    organizer.process_downloads()

    assert tiny_file.exists()
    assert not (settings.movie_folder / tiny_file.name).exists()


def test_video_type_helpers():
    assert FileOrganizer.is_tv_episode("Show.S01E01.mkv")
    assert FileOrganizer.is_tv_episode("Show.1x02.mp4")
    assert FileOrganizer.is_valid_video_file("Movie.2024.mkv")
    assert not FileOrganizer.is_valid_video_file("sample.Movie.2024.mkv")
    assert not FileOrganizer.is_valid_video_file("readme.txt")
    assert FileOrganizer.is_torrent_part("file.part")
