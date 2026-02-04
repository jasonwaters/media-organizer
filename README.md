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

## Local Development

1. Clone the repo
   ```bash
   git clone https://github.com/jasonwaters/media-organizer.git
   cd media-organizer
   ```

2. Create a virtual environment
   ```bash
   virtualenv --no-site-packages env
   source env/bin/activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.pip
   ```

4. Configure (choose one):
   
   **Option A: Environment variables (recommended)**
   ```bash
   export DOWNLOAD_FOLDER=/path/to/downloads
   export TV_FOLDER=/path/to/tv
   export MOVIE_FOLDER=/path/to/movies
   export TRASH_FOLDER=/path/to/trash
   # ... set other vars as needed
   ```
   
   **Option B: Modify `local_settings.py` temporarily**
   ```python
   # Edit local_settings.py and hardcode values
   DOWNLOAD_FOLDER = "/Users/you/Downloads"
   # (just don't commit changes)
   ```

5. Run it
   ```bash
   ./runner.py
   ```

6. Schedule with cron (optional)
   ```bash
   # Add to crontab
   */30 * * * * /path/to/env/bin/python /path/to/runner.py
   ```


## Docker

### Quick Start with Docker Compose (Recommended)

Add to your existing `docker-compose.yml`:

```yaml
services:
  media-organizer:
    image: ghcr.io/jasonwaters/media-organizer:latest
    volumes:
      - /volume1/media:/media  # Adjust to your media folder
    environment:
      DOWNLOAD_FOLDER: /media/downloads
      TV_FOLDER: /media/tv
      MOVIE_FOLDER: /media/movies
      TRASH_FOLDER: /media/trash
      SONARR_API_URL: http://sonarr:8989/api/v3
      SONARR_API_KEY: your_api_key_here
      SONARR_TV_FOLDER: /media/tv/
      TRANSMISSION_HOST: transmission
      TRANSMISSION_PORT: 9091
      TRANSMISSION_USER: your_user
      TRANSMISSION_PASSWORD: your_password
    restart: "no"
    profiles: ["manual"]  # Exclude from 'docker-compose up'
```

**Run on schedule or manually:**

```bash
# From any directory
docker-compose -f /path/to/docker-compose.yml run --rm media-organizer

# Or if in the same directory
docker-compose run --rm media-organizer
```

### Automated Image Publishing

Docker images are automatically built and published to GitHub Container Registry on every push via GitHub Actions. Images support both `linux/amd64` and `linux/arm64` architectures.

**Available tags:**
- `latest` - Latest build from main branch
- `main` - Latest main branch
- `v1.0.0` - Specific version tags
- `main-abc1234` - Specific commit

### Manual Build (Development)

```bash
# Clone repo
git clone https://github.com/jasonwaters/media-organizer.git
cd media-organizer

# Build image
docker build -t media-organizer .

# Run with environment variables
docker run --rm \
  -v /volume1/media:/media \
  -e DOWNLOAD_FOLDER=/media/downloads \
  -e TV_FOLDER=/media/tv \
  -e MOVIE_FOLDER=/media/movies \
  -e TRASH_FOLDER=/media/trash \
  -e TRANSMISSION_HOST=192.168.1.100 \
  -e TRANSMISSION_PORT=9091 \
  media-organizer
```

### Configuration Options

All configuration is done via environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DOWNLOAD_FOLDER` | Yes | `/media/downloads` | Folder to scan for downloads |
| `TV_FOLDER` | Yes | `/media/tv` | Destination for TV episodes |
| `MOVIE_FOLDER` | Yes | `/media/movies` | Destination for movies |
| `TRASH_FOLDER` | Yes | `/media/trash` | Folder for deleted items |
| `SONARR_API_URL` | No | `http://localhost:8989/api/v3` | Sonarr API endpoint |
| `SONARR_API_KEY` | No | `""` | Sonarr API key |
| `SONARR_TV_FOLDER` | No | `/media/tv/` | TV folder path from Sonarr's perspective |
| `TRANSMISSION_HOST` | No | `localhost` | Transmission hostname/IP |
| `TRANSMISSION_PORT` | No | `9091` | Transmission port |
| `TRANSMISSION_USER` | No | `""` | Transmission username |
| `TRANSMISSION_PASSWORD` | No | `""` | Transmission password |

Set these directly in your `docker-compose.yml` environment section (see examples above).
