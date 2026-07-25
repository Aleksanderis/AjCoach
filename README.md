# AjCoach 🏀🏋️‍♂️

An adaptive strength & conditioning coach that pulls your Garmin biometrics (HRV, sleep,
resting HR, training readiness) and uses them to guide daily training decisions:
traffic-light recovery status, load adjustments, and exercise swaps. Implemented as a
set of Claude Code skills plus a small Python data pipeline. Workout routines live in
[Hevy](https://www.hevyapp.com/) as stable templates; you train by opening Hevy, not by
asking the AI what to do every session.

## Quick Start

1. **Create a persona:** copy `personas/Alex/` to `personas/<YourName>/` and fill in
   `profile.md` with your own details (sport, HR zones, medical constraints).
2. **Set up credentials:** copy `personas/<YourName>/.env.example` (if present) or create
   `personas/<YourName>/.env` with your `GARMIN_EMAIL`, `GARMIN_PASSWORD`, and
   `HEVY_API_KEY`. This file is gitignored, never commit it.
3. **Authenticate Garmin:** run `python login_garmin.py` once to save your session tokens
   to `personas/<YourName>/.garmin_tokens/` (also gitignored).
4. **Generate your program:** in Claude Code, run `/create-plan` to set your goals and
   have Claude write `program/current_plan.md`, this week's schedule, and push your
   routines to Hevy.
5. **Sync data on demand:** run `python coach.py --persona <YourName>` to sync Garmin and
   generate a data snapshot, or just use `/pre-workout`, `/post-workout`, or
   `/review-activity`; they run the sync for you.

See `CLAUDE.md` for the full skill reference, file structure, and coaching protocols.

## Project Structure

- `coach.py`: syncs Garmin data and generates today's data snapshot.
- `src/report.py`: builds the markdown data snapshot from synced Garmin data.
- `src/garmin_service.py`: Garmin Connect sync (biometrics + activities).
- `src/hevy_service.py`: direct Hevy API CLI (routines, folders, exercise history).
- `src/setup_hevy.py` / `personas/<name>/setup_hevy.py`: source of truth for each
  persona's Hevy routine structure (exercises, warm-ups, sets, reps, starting weights).
- `personas/<name>/`: one folder per athlete, profile, program, synced stats, and
  coaching reports. See `CLAUDE.md` for the full layout.
- `.claude/skills/`: the `/create-plan`, `/weekly-review`, `/pre-workout`,
  `/post-workout`, `/review-activity`, and `/sync-hevy` skills.

## Core Principles

- **Auto-Deload:** if HRV, sleep score, or training readiness drops significantly, the
  coach reduces load/volume and swaps high-axial exercises for joint-friendly alternatives.
- **Recovery-Driven:** every session starts from a traffic-light recovery assessment
  (🟢/🟡/🔴) computed from 7-day rolling Garmin averages.
- **Stable Routines:** Hevy routines are templates you follow directly. The AI adjusts
  guidance around them, not the routines themselves, on every session.
