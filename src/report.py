"""
report.py — AjCoach Data Snapshot Generator
--------------------------------------------
Collects and pre-aggregates data for a persona, writes a compact markdown
data snapshot for the AI coach to read. Does NOT do coaching analysis.

Usage:
    python -m src.report --persona Alex [--days 7] [--history]
"""
import csv
import glob
import os
import re
import sys
import datetime
import argparse
from collections import defaultdict
from dotenv import load_dotenv

from .analysis_engine import load_biometric_entries, compute_biometric_summary


PERSONAS_DIR = "personas"
BASKETBALL_HISTORY_MONTHS = 6


def resolve_persona_paths(name: str) -> dict:
    base = os.path.join(PERSONAS_DIR, name)
    if not os.path.isdir(base):
        raise FileNotFoundError(f"Persona directory not found: {base}")
    env_path = os.path.join(base, ".env")
    load_dotenv(env_path, override=True)
    return {
        "name": name,
        "base_dir": base,
        "profile_path": os.path.join(base, "profile.md"),
        "stats_dir": os.path.join(base, "stats"),
        "reports_dir": os.path.join(base, "reports"),
        "biometrics_csv": os.path.join(base, "stats", "garmin_biometrics.csv"),
        "activities_csv": os.path.join(base, "stats", "garmin_activities.csv"),
        "feedback_csv": os.path.join(base, "stats", "user_feedback.csv"),
    }


def extract_profile_summary(profile_path: str) -> dict:
    """Extract key fields from profile.md without embedding the whole file."""
    if not os.path.exists(profile_path):
        return {"error": "profile.md not found"}

    name = os.path.basename(os.path.dirname(profile_path))

    with open(profile_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract HR zones — athletic column (3rd pipe-separated column in the zone table)
    # Handles both bolded (**116 - 143 bpm**) and plain (97 - 115 bpm) formats
    hr_zones = {}
    for line in content.splitlines():
        m = re.match(r"\|\s*\*\*Zone (\d+)\*\*.*?\|\s*[^|]+\|\s*\**(\d+)\s*-\s*(\d+)", line)
        if m:
            hr_zones[f"Z{m.group(1)}"] = f"{m.group(2)}–{m.group(3)}"

    # Extract primary sport
    sport_match = re.search(r"\*\s*\*\*Primary Sport:\*\*\s*(.+)", content)
    sport = sport_match.group(1).rstrip('.').strip() if sport_match else "Athlete"

    # Extract key constraints from section 6
    constraints = []
    if "lower back" in content.lower():
        constraints.append("Chronic lower back tightness — strengthen progressively, no heavy axial load on Yellow/Red")
    if "asthma" in content.lower() or "bronchial" in content.lower() or "airway" in content.lower():
        constraints.append("Suspected bronchial hyperreactivity — strict Zone 2 cardio (116–143 bpm at 7 km/h)")

    zones_str = " | ".join(f"{k} {v} bpm" for k, v in hr_zones.items()) if hr_zones else "see profile.md"

    return {
        "name": name,
        "sport": sport,
        "constraints": constraints,
        "hr_zones": zones_str,
    }


def load_biometrics_window(path: str, days: int = 14) -> list:
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append({k: (None if v == 'N/A' else v) for k, v in row.items()})
    return entries[-days:]


def load_activities_window(path: str, days: int = 7) -> list:
    if not os.path.exists(path):
        return []
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    entries = []
    with open(path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Date', '') >= cutoff:
                entries.append({k: (None if v == 'N/A' else v) for k, v in row.items()})
    return entries


def load_basketball_trend(path: str, months: int = 6) -> list:
    """Group basketball sessions by month for endurance trend analysis."""
    if not os.path.exists(path):
        return []
    cutoff = (datetime.date.today() - datetime.timedelta(days=months * 30)).isoformat()
    monthly = defaultdict(list)

    with open(path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Type', '').lower() != 'basketball':
                continue
            date = row.get('Date', '')
            if date < cutoff:
                continue
            month = date[:7]  # YYYY-MM
            try:
                duration_min = round(float(row['Duration']) / 60, 1) if row.get('Duration') else None
                avg_hr = int(float(row['AvgHR'])) if row.get('AvgHR') and row['AvgHR'] != 'N/A' else None
                max_hr = int(float(row['MaxHR'])) if row.get('MaxHR') and row['MaxHR'] != 'N/A' else None
                z4 = float(row['Zone4_Mins']) if row.get('Zone4_Mins') and row['Zone4_Mins'] != 'N/A' else 0
                z5 = float(row['Zone5_Mins']) if row.get('Zone5_Mins') and row['Zone5_Mins'] != 'N/A' else 0
                monthly[month].append({
                    "duration": duration_min,
                    "avg_hr": avg_hr,
                    "max_hr": max_hr,
                    "z4_z5_mins": round(z4 + z5, 1)
                })
            except (ValueError, TypeError):
                continue

    trend = []
    for month in sorted(monthly.keys()):
        sessions = monthly[month]
        durations = [s["duration"] for s in sessions if s["duration"] is not None]
        avg_hrs = [s["avg_hr"] for s in sessions if s["avg_hr"] is not None]
        max_hrs = [s["max_hr"] for s in sessions if s["max_hr"] is not None]
        z45_list = [s["z4_z5_mins"] for s in sessions]
        trend.append({
            "month": month,
            "sessions": len(sessions),
            "avg_duration_min": round(sum(durations) / len(durations), 1) if durations else None,
            "avg_hr": round(sum(avg_hrs) / len(avg_hrs)) if avg_hrs else None,
            "max_hr": max(max_hrs) if max_hrs else None,
            "avg_z4z5_mins": round(sum(z45_list) / len(z45_list), 1) if z45_list else None,
        })
    return trend


def load_feedback(path: str, days: int = 7) -> list:
    if not os.path.exists(path):
        return []
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    entries = []
    with open(path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Date', '') >= cutoff:
                entries.append(dict(row))
    return entries


def find_last_high_intensity_activity(activities_path: str) -> dict | None:
    """Find the most recent basketball or high-intensity activity."""
    if not os.path.exists(activities_path):
        return None
    last = None
    with open(activities_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            act_type = row.get('Type', '').lower()
            if act_type in ('basketball', 'running', 'cycling', 'soccer', 'tennis'):
                if last is None or row.get('Date', '') > last.get('Date', ''):
                    last = dict(row)
    return last




def load_program_files(persona_base: str) -> dict:
    """Load current_plan.md and current week plan if they exist."""
    program_dir = os.path.join(persona_base, "program")
    result = {}

    plan_path = os.path.join(program_dir, "current_plan.md")
    if os.path.exists(plan_path):
        with open(plan_path, 'r', encoding='utf-8') as f:
            result["current_plan"] = f.read()

    # Find current week file: week_YYYY-MM-DD.md — pick the most recent one
    week_files = sorted(glob.glob(os.path.join(program_dir, "week_*.md")))
    if week_files:
        week_path = week_files[-1]
        with open(week_path, 'r', encoding='utf-8') as f:
            result["week_plan"] = f.read()
            result["week_plan_file"] = week_path

    return result


def parse_today_session_type(week_plan_content: str) -> str | None:
    """
    Look for today's weekday in the week plan and extract the session type.
    Looks for lines like: '**Monday** — Strength (Upper)' or '| Monday | Strength |'
    """
    if not week_plan_content:
        return None
    today_name = datetime.date.today().strftime("%A")  # e.g. "Monday"
    for line in week_plan_content.splitlines():
        if today_name.lower() in line.lower():
            # Extract everything after the day name
            parts = line.split(today_name, 1)[-1] if today_name in line else \
                    line.split(today_name.lower(), 1)[-1]
            # Clean up markdown syntax
            cleaned = re.sub(r'[|*_`]', '', parts).strip(' -–:')
            if cleaned:
                return cleaned[:80]  # cap length
    return None




def generate_markdown(persona: dict, mode: str, days: int, history: bool) -> str:
    today = datetime.date.today().isoformat()
    profile = extract_profile_summary(persona["profile_path"])
    all_entries = load_biometric_entries(persona["biometrics_csv"])
    bio_window = load_biometrics_window(persona["biometrics_csv"], days=90 if history else 14)
    activities = load_activities_window(persona["activities_csv"], days=days)
    basketball_trend = load_basketball_trend(persona["activities_csv"], months=BASKETBALL_HISTORY_MONTHS)
    feedback = load_feedback(persona["feedback_csv"], days=days)
    last_hia = find_last_high_intensity_activity(persona["activities_csv"])
    stats = compute_biometric_summary(all_entries)
    program = load_program_files(persona["base_dir"])
    today_session_type = parse_today_session_type(program.get("week_plan", ""))

    md = []
    md.append(f"# AjCoach Data Snapshot — {persona['name']}")
    md.append(f"**Date:** {today} | **Mode:** {mode.upper()} | **Window:** {days} days{'  *(history mode)*' if history else ''}\n")

    # Compact profile summary
    md.append("## Athlete")
    md.append(f"**{profile.get('name')}** | {profile.get('sport')}")
    for c in profile.get('constraints', []):
        md.append(f"- {c}")
    md.append(f"\n**HR Zones (athletic):** {profile.get('hr_zones')}\n")

    # Computed recovery metrics
    md.append("## Computed Recovery Metrics")
    hrv_date = stats.get('hrv_today_date', today)
    hrv_label = "HRV" if hrv_date == today else f"HRV (latest: {hrv_date})"
    hrv_line = f"{hrv_label}: {stats.get('hrv_today')}ms"
    if stats.get('hrv_7d_avg') is not None:
        delta = stats.get('hrv_delta_pct')
        delta_str = f"{delta:+.1f}%" if delta is not None else "N/A"
        hrv_line += f" | 7d avg: {stats.get('hrv_7d_avg')}ms | Delta: {delta_str}"
    if stats.get('hrv_trend') and stats.get('hrv_trend') != 'unknown':
        hrv_line += f" | Trend: {stats.get('hrv_trend')} ({stats.get('hrv_5d_sequence')})"
    md.append(f"- {hrv_line}")

    rhr_date = stats.get('rhr_today_date', today)
    rhr_label = "Resting HR" if rhr_date == today else f"Resting HR (latest: {rhr_date})"
    rhr_line = f"{rhr_label}: {stats.get('rhr_today')} bpm"
    if stats.get('rhr_7d_avg') is not None:
        delta = stats.get('rhr_delta_pct')
        delta_str = f"{delta:+.1f}%" if delta is not None else "N/A"
        rhr_line += f" | 7d avg: {stats.get('rhr_7d_avg')} bpm | Delta: {delta_str}"
    md.append(f"- {rhr_line}")

    md.append(f"- Training Readiness today: {stats.get('readiness_today') or 'N/A'}")

    if stats.get('sleep_data_gap'):
        md.append("- Sleep Score: **DATA GAP** — not syncing for past 7+ days (investigate Garmin API)")
    else:
        md.append(f"- Sleep Score today: {stats.get('sleep_today') or 'N/A'} | 7d avg: {stats.get('sleep_7d_avg') or 'N/A'}")

    if last_hia:
        try:
            last_date = datetime.date.fromisoformat(last_hia['Date'])
            days_ago = (datetime.date.today() - last_date).days
            dur_min = round(float(last_hia.get('Duration', 0)) / 60, 0)
            md.append(f"- Last high-intensity activity: **{last_hia.get('Name')}** on {last_hia['Date']} ({days_ago} days ago, {dur_min:.0f} min, avg HR {last_hia.get('AvgHR') or 'N/A'})")
        except Exception:
            pass

    if today_session_type:
        md.append(f"- **Today's planned session:** {today_session_type}")
    elif program.get("week_plan"):
        md.append("- Today's session type: *not found in week plan — check day name*")
    else:
        md.append("- **No week plan found.** Run `/weekly-review` to generate one.")
    md.append("")

    # Biometrics table — suppress all-null columns
    md.append(f"## Recent Biometrics (Last {'90' if history else '14'} Days)")
    cols = [
        'Date', 'HRV', 'SleepScore', 'RestingHR', 'TrainingReadiness',
        'ActiveCalories', 'IntensityMinutes', 'ActivityCount',
        'Steps', 'AvgStress', 'BodyBatteryHigh', 'BodyBatteryLow',
        'HydrationMl', 'SleepDurationMin', 'SleepDeepMin', 'SleepRemMin', 'SleepLightMin',
        'SpO2Avg', 'BreathingRate', 'WeightKg',
    ]
    col_labels = [
        'Date', 'HRV', 'Sleep', 'RHR', 'Readiness',
        'Kcal', 'IntMin', 'Acts',
        'Steps', 'Stress', 'BB↑', 'BB↓',
        'H2O(ml)', 'SleepMin', 'Deep', 'REM', 'Light',
        'SpO2%', 'BPM', 'Weight(kg)',
    ]
    active_cols = [c for c in cols if any(row.get(c) is not None for row in bio_window)]
    active_labels = [col_labels[cols.index(c)] for c in active_cols]

    md.append("| " + " | ".join(active_labels) + " |")
    md.append("|" + "|".join(":---:" for _ in active_labels) + "|")
    for row in bio_window:
        md.append("| " + " | ".join(str(row.get(c) or 'N/A') for c in active_cols) + " |")

    null_cols = [col_labels[cols.index(c)] for c in cols if c not in active_cols and c != 'Date']
    if null_cols:
        md.append(f"*Columns suppressed (all N/A): {', '.join(null_cols)}*")
    md.append("")

    # Recent activities
    md.append(f"## Recent Activities (Last {days} Days)")
    if activities:
        md.append("| Date | Name | Type | Duration (min) | Avg HR | Max HR | Z1 | Z2 | Z3 | Z4 | Z5 |")
        md.append("|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
        for a in activities:
            try:
                dur = round(float(a.get('Duration', 0)) / 60, 1)
            except Exception:
                dur = 0.0
            md.append(f"| {a.get('Date')} | {a.get('Name')} | {a.get('Type')} | {dur} | {a.get('AvgHR') or 'N/A'} | {a.get('MaxHR') or 'N/A'} | {a.get('Zone1_Mins') or 'N/A'} | {a.get('Zone2_Mins') or 'N/A'} | {a.get('Zone3_Mins') or 'N/A'} | {a.get('Zone4_Mins') or 'N/A'} | {a.get('Zone5_Mins') or 'N/A'} |")
    else:
        md.append("*No activities in this window.*")
    md.append("")

    # Basketball trend
    md.append(f"## Basketball Trend (Last {BASKETBALL_HISTORY_MONTHS} Months)")
    if basketball_trend:
        md.append("| Month | Sessions | Avg Duration | Avg HR | Peak HR | Avg Z4+Z5 mins |")
        md.append("|:---|:---:|:---:|:---:|:---:|:---:|")
        for row in basketball_trend:
            md.append(f"| {row['month']} | {row['sessions']} | {row['avg_duration_min']} min | {row['avg_hr'] or 'N/A'} | {row['max_hr'] or 'N/A'} | {row['avg_z4z5_mins']} min |")
    else:
        md.append("*No basketball sessions in this period.*")
    md.append("")

    # User feedback
    md.append("## User Feedback")
    if feedback:
        md.append("| Date | Pain | Notes |")
        md.append("|:---|:---:|:---|")
        for f in feedback:
            md.append(f"| {f.get('Date')} | {f.get('PainLevel')}/10 | {f.get('Text')} |")
    else:
        md.append("*No feedback logged in this window.*")
    md.append("")

    # Workout tracking is handled live via hevy_service.py during coaching sessions
    md.append("## Workout Tracking")
    md.append("*Routines and exercise history are fetched live from Hevy via `src/hevy_service.py` during coaching sessions.*")
    md.append("")

    # Program plan
    md.append("## Training Program")
    if program.get("current_plan"):
        md.append(f"*File: `program/current_plan.md`*\n")
        md.append(program["current_plan"])
    else:
        md.append("*No program plan yet. Use `/create-plan` to generate one.*")
    md.append("")

    if program.get("week_plan"):
        week_file = os.path.basename(program.get("week_plan_file", "week plan"))
        md.append(f"## This Week's Plan (`{week_file}`)")
        md.append(program["week_plan"])
    else:
        md.append("## This Week's Plan")
        md.append("*No week plan yet. Use `/weekly-review` to generate one.*")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="Generate AjCoach compact data snapshot.")
    parser.add_argument("--persona", "-p", required=True, help="Persona name (e.g. 'Alex')")
    parser.add_argument("--days", type=int, default=7, help="Activity/feedback window in days")
    parser.add_argument("--mode", choices=["pre", "post"], default="pre")
    parser.add_argument("--history", action="store_true", help="Load 90-day biometrics for deep analysis")
    args = parser.parse_args()

    try:
        persona = resolve_persona_paths(args.persona)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(persona["reports_dir"], exist_ok=True)
    today = datetime.date.today().isoformat()

    md_content = generate_markdown(persona, args.mode, args.days, args.history)

    md_path = os.path.join(persona["reports_dir"], f"{today}_data.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f"Data snapshot saved: {md_path}", file=sys.stderr)
    print(md_path)


if __name__ == "__main__":
    main()
