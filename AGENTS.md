# AGENTS.md

This file defines project-specific guidance for AI/code agents working in this repository.

## Project Goal

Maintain and evolve a reliable media post-processing tool that:

- removes completed torrents from Transmission
- extracts RAR archives from downloads
- moves media files into TV/Movie folders
- cleans processed folders into trash
- notifies Sonarr to import/rename TV content

Preserve behavior unless the task explicitly requests changes.

## Tech Stack

- Python 3.12
- `requests`
- `transmission-rpc`
- `pytest`
- Docker image runtime

## Local Setup

Use conda and editable install:

```bash
conda env create -f environment.yml
conda activate media-organizer
```

If needed in an existing environment:

```bash
pip install -e '.[dev]' --no-build-isolation
```

## Common Commands

Run app:

```bash
python runner.py
```

Run tests:

```bash
pytest -q
```

Run coverage:

```bash
python -m coverage run -m pytest -q
python -m coverage report -m
```

## Architecture Notes

- `media_organizer/config.py`: typed settings + env parsing/validation
- `media_organizer/app.py`: domain logic/services
  - `TransmissionService`
  - `FileOrganizer`
  - `SonarrService`
  - `MediaOrganizer` orchestration
- `media_organizer/cli.py`: wiring/runtime entry
- `runner.py`: compatibility entrypoint

## Coding Expectations

- Keep functions focused and small.
- Prefer explicit names over short/clever names.
- Avoid broad exception handlers unless justified by cron/survivability needs.
- Catch operational exceptions (`OSError`, request/network exceptions) and allow programming bugs to surface.
- Use dependency injection for IO clients to keep code testable.
- Avoid introducing global mutable state.

## Testing Expectations

- Add or update tests with every behavior change.
- Cover happy paths and edge/failure paths.
- Prefer deterministic tests using fakes/mocks over live service calls.
- Do not weaken assertions just to pass tests.
- Keep tests independent and fast.

## Behavior-Safety Rules

- Never delete download root itself.
- Preserve root-safety guards and cleanup semantics.
- Preserve existing filename classification behavior unless explicitly requested.
- Keep Sonarr call pacing configurable via `SONARR_COMMAND_DELAY_SECONDS`.

## CI/Release Rules

- Docker publish workflow must run tests before build/push.
- Any test failure must block image publication.

## Documentation

When adding config/env vars or behavior, update:

- `README.md`
- `environment.yml` (if setup changes)
- tests validating the new behavior
