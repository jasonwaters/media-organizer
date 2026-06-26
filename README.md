Media Organizer
===============

Python 3 media post-processing script for Transmission + Sonarr workflows.

## What It Does

On each run, it:

- Removes completed torrents from Transmission (without deleting data)
- Decompresses `.nsz` files to `.nsp` and moves Nintendo Switch game files to a dedicated folder (optional)
- Scans a download folder recursively
- Extracts RAR archives
- Moves video files to TV or Movie folders based on filename patterns
- Cleans up processed folders into a trash folder
- Calls Sonarr to import/rename newly moved TV episodes

## Requirements

- Python 3.10+ (tested with 3.12)
- `unrar` binary available on `PATH` (Docker image installs official `unrar`)
- Transmission RPC access (optional but expected for torrent cleanup)
- Sonarr API access (optional but expected for TV import/rename)

## Local Development with Conda (Recommended)

1. Create and activate the environment:

```bash
conda env create -f environment.yml
conda activate media-organizer
```

This installs the project in editable mode with dev dependencies.

2. Configure environment variables:

```bash
export DOWNLOAD_FOLDER=/path/to/downloads
export TV_FOLDER=/path/to/tv
export MOVIE_FOLDER=/path/to/movies
export TRASH_FOLDER=/path/to/trash

export SONARR_API_URL=http://localhost:8989/api/v3
export SONARR_API_KEY=your_key
export SONARR_TV_FOLDER=/path/that/sonarr/sees/tv/
export SONARR_COMMAND_DELAY_SECONDS=0

export TRANSMISSION_HOST=localhost
export TRANSMISSION_PORT=9091
export TRANSMISSION_USER=your_user
export TRANSMISSION_PASSWORD=your_password
```

3. Run the organizer:

```bash
python runner.py
```

4. Run tests:

```bash
pytest
```

## Configuration

All runtime configuration is loaded from environment variables.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DOWNLOAD_FOLDER` | Yes | `/media/downloads` | Folder to scan for downloads |
| `TV_FOLDER` | Yes | `/media/tv` | Destination for TV episodes |
| `MOVIE_FOLDER` | Yes | `/media/movies` | Destination for movie files |
| `TRASH_FOLDER` | Yes | `/media/trash` | Destination for cleaned-up folders |
| `SONARR_API_URL` | No | `http://localhost:8989/api/v3` | Sonarr API base URL |
| `SONARR_API_KEY` | No | `""` | Sonarr API key |
| `SONARR_TV_FOLDER` | No | `/media/tv/` | TV path from Sonarr's perspective |
| `SONARR_COMMAND_DELAY_SECONDS` | No | `0` | Delay between Sonarr command posts |
| `TRANSMISSION_HOST` | No | `localhost` | Transmission hostname |
| `TRANSMISSION_PORT` | No | `9091` | Transmission RPC port |
| `TRANSMISSION_USER` | No | `""` | Transmission username |
| `TRANSMISSION_PASSWORD` | No | `""` | Transmission password |
| `SWITCH_FOLDER` | No | `""` | Destination for Switch game files (disabled if empty) |

## Scheduling

Example cron entry (every 30 minutes):

```bash
*/30 * * * * /path/to/conda/envs/media-organizer/bin/python /path/to/media-organizer/runner.py
```

## Docker

Example `docker-compose.yml` service:

```yaml
services:
  media-organizer:
    image: ghcr.io/jasonwaters/media-organizer:latest
    volumes:
      - /volume1/media:/media
      - /volume1/downloads:/downloads
      - /volume1/docker/media-organizer/config:/config
    environment:
      DOWNLOAD_FOLDER: /downloads/_complete
      TV_FOLDER: /media/tv
      MOVIE_FOLDER: /media/movies
      TRASH_FOLDER: /downloads/#recycle
      SONARR_API_URL: http://sonarr:8989/api/v3
      SONARR_API_KEY: your_api_key_here
      SONARR_TV_FOLDER: /media/tv/
      SONARR_COMMAND_DELAY_SECONDS: 5
      TRANSMISSION_HOST: transmission
      TRANSMISSION_PORT: 9091
      TRANSMISSION_USER: ""
      TRANSMISSION_PASSWORD: ""
      SWITCH_FOLDER: /downloads/switch
    restart: "no"
```

### Nintendo Switch Support

To enable `.nsz` decompression, place your `prod.keys` or `keys.txt` file in the
`/config` volume mount. The Docker image symlinks both filenames to the location
where `nsz` expects them (`/root/.switch/`). Without keys, `.nsz` files are still
moved to `SWITCH_FOLDER` but won't be decompressed.

Run manually:

```bash
docker-compose run --rm media-organizer
```

Verify container dependencies are installed correctly:

```bash
docker-compose run --rm media-organizer python runner.py --check
```

## Project Layout

- `runner.py`: compatibility entrypoint
- `media_organizer/config.py`: typed environment settings
- `media_organizer/app.py`: core services and orchestration
- `media_organizer/cli.py`: app wiring and startup
- `tests/`: pytest unit tests
