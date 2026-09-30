# AjCoach 🏀🏋️‍♂️

**Adaptive strength & conditioning coaching powered by your Garmin biometrics and Claude Code.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Built with Claude Code](https://img.shields.io/badge/built%20with-Claude%20Code-blueviolet?logo=anthropic&logoColor=white)](https://claude.ai/code)

<a href="https://www.buymeacoffee.com/aleksanderis"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="40"></a>

---

AjCoach pulls your Garmin biometrics — HRV, sleep score, resting HR, and training readiness — and uses them to guide daily training decisions: traffic-light recovery status, load adjustments, and exercise swaps. Implemented as a set of [Claude Code](https://claude.ai/code) skills plus a small Python data pipeline.

Workout routines live in [Hevy](https://www.hevyapp.com/) as stable templates. You train by opening Hevy; the AI guides load and recovery decisions, not every rep.

## Features

- **Recovery-driven traffic light** — 🟢 / 🟡 / 🔴 assessment from 7-day rolling Garmin averages before every session
- **Auto-deload** — HRV drop, poor sleep, or low training readiness automatically reduces load/volume and swaps high-axial exercises for joint-friendly alternatives
- **Hevy integration** — routines pushed directly to Hevy via API; open the app and train, no manual setup
- **Multi-persona** — one repo, one folder per athlete; useful for coaches managing multiple athletes
- **Nutrition planning** — optional fat-loss/nutrition protocol alongside the training plan
- **Claude Code skills** — `/pre-workout`, `/post-workout`, `/weekly-review`, `/create-plan`, `/review-activity`, `/sync-hevy`

## Quick Start

1. **Create a persona** — copy `personas/Alex/` to `personas/<YourName>/` and fill in `profile.md` with your sport, HR zones, and medical constraints.
2. **Set credentials** — create `personas/<YourName>/.env` with:
   ```
   GARMIN_EMAIL=you@example.com
   GARMIN_PASSWORD=yourpassword
   HEVY_API_KEY=your_hevy_key
   ```
   This file is gitignored — never commit it.
3. **Authenticate Garmin** — run once to save session tokens:
   ```bash
   python login_garmin.py
   ```
4. **Generate your program** — in Claude Code, run `/create-plan` to set goals and have Claude write your training plan and push routines to Hevy.
5. **Sync data on demand** — run before any coaching session:
   ```bash
   python coach.py --persona <YourName>
   ```
   Or just invoke a skill — `/pre-workout`, `/post-workout`, `/review-activity` run the sync for you.

See [`CLAUDE.md`](CLAUDE.md) for the full skill reference, file structure, and coaching protocols.

## Project Structure

```
.
├── coach.py                  # Garmin sync + data snapshot entry point
├── login_garmin.py           # One-time Garmin auth
├── requirements.txt
├── src/
│   ├── report.py             # Builds markdown data snapshot from synced Garmin data
│   ├── garmin_service.py     # Garmin Connect sync (biometrics + activities)
│   ├── hevy_service.py       # Direct Hevy API CLI (routines, history)
│   ├── setup_hevy.py         # Hevy routine loader (imports persona-specific setup)
│   └── custom_exercise_templates.md
├── personas/
│   └── <name>/
│       ├── profile.md        # Athlete profile, HR zones, protocols
│       ├── setup_hevy.py     # Routine structure (exercises, sets, weights)
│       ├── .env              # Credentials (gitignored)
│       ├── stats/            # Synced Garmin CSVs
│       ├── program/          # current_plan.md, week schedules, nutrition plan
│       └── reports/          # YYYY-MM-DD_data.md + coaching reports
└── .claude/
    └── skills/               # /create-plan, /weekly-review, /pre-workout, etc.
```

## Skill Reference

| Skill | When to use | Output |
|---|---|---|
| `/create-plan` | New season, goals change, injury | `current_plan.md` + week schedule + Hevy routines |
| `/weekly-review` | Every Sunday | Next week's schedule; Hevy update if exercises change |
| `/pre-workout` | Before a session | `YYYY-MM-DD_coaching.md` with traffic light + load guidance |
| `/post-workout` | After a session | Appends session review to coaching report |
| `/review-activity` | Any time | Ad-hoc answer about Garmin stats, trends, or activities |
| `/sync-hevy` | After editing `setup_hevy.py` | Pushes updated routines to Hevy |

## Recovery Traffic Light

| Signal | Flag threshold |
|---|---|
| HRV | Drop > 15% vs 7-day average |
| Sleep Score | < 60 |
| Training Readiness | < 40 |
| Resting HR | > 5% above 7-day average |
| High-intensity activity | Only flagged within last 48 h |
| Subjective pain | > 3/10 or acute joint mention |

- 🟢 **Green** — all nominal → full planned load
- 🟡 **Yellow** — 1–2 mild flags → same load, −10–20% volume
- 🔴 **Red** — 2+ significant flags → −15%+ load, swap high-axial lifts, add mobility

## Running with Docker

The `docker/` directory contains a compose setup that runs AjCoach inside a container with [cloudcli](https://github.com/cloudcli-ai/cloudcli) — a browser-based web UI for Claude Code CLI. Useful for NAS / home-server deployments where you want to access the coach from any device without a local Claude Code install.

```
docker/
├── Dockerfile               # Extends claude-code sandbox image, adds Python + cloudcli
├── docker-compose.yml       # Linux/Mac
├── docker-compose-win.yml   # Windows host path variant
└── entrypoint.sh
```

1. Build the image:
   ```bash
   docker build -f docker/Dockerfile -t ajcoach:latest .
   ```
2. Edit path placeholders in `docker/docker-compose.yml`, then:
   ```bash
   docker compose -f docker/docker-compose.yml up -d
   ```
3. Open `http://<host>:3001` — Claude Code web UI served by cloudcli.

## Requirements

- Python 3.10+
- [Claude Code](https://claude.ai/code) CLI (or Docker + cloudcli for headless use)
- Garmin Connect account with a compatible device
- [Hevy](https://www.hevyapp.com/) account + API key

Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Support

If you find this useful — <a href="https://www.buymeacoffee.com/aleksanderis">buy me a coffee ☕</a>
