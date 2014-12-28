#!/usr/bin/env python
import shutil
import datetime

from local_settings import DOWNLOAD_FOLDER, TRANSMISSION_HOST, TRANSMISSION_USER, TRANSMISSION_PORT, \
    TRANSMISSION_PASSWORD, MOVIE_FOLDER, TV_FOLDER, TRASH_FOLDER
import os
import re
import transmissionrpc
from transmissionrpc.error import TransmissionError


class FlagFile:
    def __init__(self):
        pass

    REMOVE_FOLDER = '.removefolder'
    UNRARED = '.unrared'


def log(message):
    now = datetime.datetime.now()
    print "%s (%s)\n" % (message, now.strftime("%Y-%m-%d %H:%M:%S"))


class Organizer(object):
    def __init__(self):
        self.PATTERN_EPISODE = re.compile(".*((([sS]\d{1,2}[eE]\d{1,2})|(\d+x\d+))|(\.\d{3}\.)).*")
        self.PATTERN_VIDEO = re.compile("(^.+\.(avi|mp4|mkv)$)")
        self.PATTERN_RAR = re.compile("^.+\.(rar|r\d+)$")

        self.extensions_unrar = ['.rar', '.r01']  # List of extensions for auto-extract to look for
        self.supported_filetypes = []
        self.supported_filetypes.extend(self.extensions_unrar)  # rar support

        self.unrar_name = 'unrar'
        self.unrar_executable = None
        self.unrar_check()

        # Check that the download directory parameters is actually a directory
        self.remove_finished_torrents()  # from transmission

        self.traverse_directories()

    '''Attempts to find unrar on the system path and return the directory unrar is found in'''

    def find_unrar(self):
        # Search the system path for the unrar executable
        for directory in os.getenv('PATH').split(os.pathsep):
            # Ensure the dir in the path is a real directory
            if os.path.exists(directory):
                files = os.listdir(directory)
                if self.unrar_name in files:
                    return directory
            else:
                # The directory in the path does not exist
                pass
        # unrar not found on this system
        return False

    '''Sanity check to make sure unrar is found on the system'''

    def unrar_check(self):
        unrar_path = self.find_unrar()

        if unrar_path:
            self.unrar_executable = os.path.join(unrar_path, self.unrar_name)
        else:
            log('Error: ' + self.unrar_name + ' not found in the system path')
            exit()

    '''Scan the download directory and its subdirectories'''

    def traverse_directories(self):
        # Search download directory and all subdirectories
        for dirname, dirnames, filenames in os.walk(DOWNLOAD_FOLDER):
            self.scan_for_archives(dirname)
            self.scan_for_videos(dirname)
            self.clean_up(dirname)

    '''Check for rar files in each directory'''

    def scan_for_archives(self, directory):
        # Look for a .rar archive in dir
        dir_listing = os.listdir(directory)
        # First archive that is found with .rar extension is extracted
        # (for directories that have more than one archives in it)
        for filename in dir_listing:
            for ext in self.supported_filetypes:
                if filename.endswith(ext):
                    # If a .rar archive is found, check to see if it has been extracted previously
                    file_unrared = os.path.exists(os.path.join(directory, FlagFile.UNRARED))
                    if not file_unrared:
                        log("Need to extract: " + filename)
                        # Start extracting file
                        self.start_unrar(directory, filename)
                    # .rar was found, dont need to search for .r01
                    break

    '''Check for video files in each directory and move them'''

    def scan_for_videos(self, directory):
        dir_listing = os.listdir(directory)

        for filename in dir_listing:
            if self.is_valid_video_file(filename):
                file_path = os.path.join(directory, filename)
                log("Moving %s..." % filename)
                if self.is_tv_episode(filename):
                    shutil.move(file_path, TV_FOLDER)
                else:
                    shutil.move(file_path, MOVIE_FOLDER)

                self.mark_directory(directory, FlagFile.REMOVE_FOLDER)
                log("Moved '%s'." % filename)

    def clean_up(self, directory):
        unrared = os.path.exists(os.path.join(directory, FlagFile.UNRARED))
        remove_folder = os.path.exists(os.path.join(directory, FlagFile.REMOVE_FOLDER))

        if unrared:
            self.delete_rars(directory)

        if remove_folder:
            self.trash_folder(directory)

    def delete_rars(self, directory):
        if directory is not DOWNLOAD_FOLDER:
            log("Deleting RARs (%s)..." % directory)
            dir_listing = os.listdir(directory)

            for filename in dir_listing:
                if self.is_rar(filename):
                    log("deleted %s" % filename)
                    os.remove(os.path.join(directory, filename))

    def trash_folder(self, directory):
        if directory is not DOWNLOAD_FOLDER:
            log("Deleting Folder...")
            shutil.move(directory, TRASH_FOLDER)

    '''Extract a rar archive'''

    def start_unrar(self, directory, archive_name):
        # Create command line arguments for rar extractions
        cmd_args = ['', '', '', '', '']
        cmd_args[0] = self.unrar_name  # unrar
        cmd_args[1] = 'e'  # command line switches: e - extract
        cmd_args[2] = '-y'  # y - assume yes to all queries (overwrite)
        cmd_args[3] = os.path.join(directory, archive_name)  # archive path
        cmd_args[4] = directory  # destination

        try:
            os.spawnv(os.P_WAIT, self.unrar_executable, cmd_args)
        except OSError:
            log('Error: ' + self.unrar_name + ' not found in the given path.')
            exit()

        # Sucessfully extracted archive, mark the dir with a hidden file
        self.mark_directory(directory, FlagFile.UNRARED)
        self.delete_rars(directory)

    '''Creates a hidden file so the same archives will not be extracted again'''

    def mark_directory(self, directory, mark_file_name):
        mark_file = os.path.join(directory, mark_file_name)
        f = open(mark_file, 'w')
        f.close()
        log(mark_file_name + ' file created')

    def is_rar(self, name):
        return self.PATTERN_RAR.match(name.lower()) is not None

    def is_tv_episode(self, name):
        return self.PATTERN_EPISODE.match(name.lower()) is not None

    def is_valid_video_file(self, name):
        return self.PATTERN_VIDEO.match(name.lower()) is not None and name.lower().find('sample') == -1

    def remove_finished_torrents(self):
        try:
            client = transmissionrpc.Client(address=TRANSMISSION_HOST, port=TRANSMISSION_PORT,
                                            user=TRANSMISSION_USER, password=TRANSMISSION_PASSWORD)

            torrents = client.get_torrents()

            for tid, torrent in torrents.iteritems():
                if torrent.progress == 100:
                    log("Removed '%s'." % torrent.name)
                    client.remove_torrent(torrent.hashString, delete_data=False)

        except TransmissionError as error:
            log("Unable to connect to Transmission.")
            log(error)


if __name__ == '__main__':
    obj = Organizer()
