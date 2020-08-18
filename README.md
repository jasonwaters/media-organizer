Media Cowboy
===============

###### Tested on OS X, but should work anywhere python 2.7 is installed.

## What is It?

A python script that:

* Removes completed torrents from Transmission.
* Scans a download folder for archives and video files.
  * Extracts archives
  * Moves archive files to Trash
  * Moves video files to a TV or Movies folder depending on filename.
  * Moves folders to Trash if a video file was moved.

## Use it

1. clone the repo
1. create a virtual environment ```virtualenv --no-site-packages env```
1. ```source env/bin/activate```
1. ```pip install -r requirements.pip```
1. copy local_settings.template.py to local_settings.py
1. provide values for all properties in local_settings.py
1. execute ```./runner.py```
1. add ```runner.py``` to a cron job to run periodically.


## Docker
1. clone the repo
1. copy local_settings.template.py to local_settings.py
1. provide values for all properties in local_settings.py from the context of `/media` within the docker container
1. switch to the repo directory from terminal
1. Build the docker image `docker build -t media-organizer .`
1. Run the command `docker run --rm -v /volume1/media/:/media media-organizer`
  * correctly specify a path to a media folder where all directories referenced in local_settings.py can be found
