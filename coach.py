import csv
import os
import sys
import datetime
import argparse
import subprocess
from dotenv import load_dotenv
from src.garmin_service import GarminService


PERSONAS_DIR = "personas"


def resolve_persona(name: str) -> dict:
    """
    Resolve all paths for a given persona name.
    Returns a dict of paths and config values.
    """
    base = os.path.join(PERSONAS_DIR, name)
    if not os.path.isdir(base):
        raise FileNotFoundError(
            f"Persona '{name}' not found. "
            f"Expected directory: {base}\n"
            f"Available personas: {list_personas()}"
        )

    env_path = os.path.join(base, ".env")
    load_dotenv(env_path, override=True)

    return {
        "name": name,
        "base_dir": base,
        "profile_path": os.path.join(base, "profile.md"),
        "stats_dir": os.path.join(base, "stats"),
        "token_dir": os.path.join(base, ".garmin_tokens"),
        "feedback_csv": os.path.join(base, "stats", "user_feedback.csv"),
        "garmin_email": os.getenv("GARMIN_EMAIL"),
        "garmin_password": os.getenv("GARMIN_PASSWORD"),
    }


def list_personas() -> list:
    if not os.path.isdir(PERSONAS_DIR):
        return []
    return [
        d for d in os.listdir(PERSONAS_DIR)
        if os.path.isdir(os.path.join(PERSONAS_DIR, d))
    ]


def get_cached_dates(biometrics_csv: str) -> set:
    """Return the set of dates already present in the biometrics CSV."""
    if not os.path.exists(biometrics_csv):
        return set()
    with open(biometrics_csv, mode='r', newline='') as f:
        reader = csv.DictReader(f)
        return {row['Date'] for row in reader if row.get('Date')}

def range_fully_cached(biometrics_csv: str, days_back: int) -> bool:
    """Return True only if every date in the requested range is already cached."""
    cached = get_cached_dates(biometrics_csv)
    today = datetime.date.today()
    return all(
        (today - datetime.timedelta(days=i)).isoformat() in cached
        for i in range(days_back)
    )



def main():
    parser = argparse.ArgumentParser(
        description="AjCoach — AI-assisted workout preparation tool."
    )
    parser.add_argument(
        "--persona", "-p",
        default=None,
        help="Persona name (e.g. 'Alex'). Auto-detected if only one persona exists."
    )
    parser.add_argument(
        "--sync-only",
        action="store_true",
        help="Only sync Garmin data, do not prompt or adapt."
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-sync Garmin data even if today's data already exists."
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Number of days to sync/report."
    )
    parser.add_argument(
        "--only-activities",
        action="store_true",
        help="Sync activities only, skip biometrics."
    )
    parser.add_argument(
        "--only-biometrics",
        action="store_true",
        help="Sync biometrics only, skip activities."
    )
    parser.add_argument(
        "--backfill-weight",
        action="store_true",
        help="Backfill WeightKg for all dates missing it (single API call). Use --force to re-fetch all."
    )
    parser.add_argument(
        "--backfill-details",
        action="store_true",
        help="Backfill splits + HR time-series for all activities missing detail files. Use --force to re-fetch all."
    )
    args = parser.parse_args()

    # Auto-detect persona if not specified
    persona_name = args.persona
    if not persona_name:
        available = list_personas()
        if len(available) == 1:
            persona_name = available[0]
            print(f"Auto-selected persona: {persona_name}")
        elif len(available) == 0:
            print("Error: No personas found in personas/ directory.")
            return
        else:
            print(f"Multiple personas found: {available}")
            print("Please specify one with --persona <name>")
            return

    # Load persona config
    try:
        persona = resolve_persona(persona_name)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    print(f"=== AjCoach: Starting Session for {persona['name']} ===")

    # Step 1: Sync Garmin data (skip if today's data already cached)
    biometrics_csv = os.path.join(persona["stats_dir"], "garmin_biometrics.csv")
    fully_cached = range_fully_cached(biometrics_csv, args.days)

    if fully_cached and not args.force:
        print(f"\n[Step 1] All {args.days} days already cached — skipping Garmin sync.")
        print(f"  Use --force to re-sync anyway.")
    else:
        if args.force:
            print(f"\n[Step 1] --force set. Re-syncing Garmin data ({args.days} days)...")
        else:
            print(f"\n[Step 1] Missing data detected. Syncing Garmin data ({args.days} days)...")

        garmin = GarminService(
            persona["garmin_email"],
            persona["garmin_password"],
            persona["token_dir"],
            persona["stats_dir"],
        )
        try:
            garmin.sync(
                days_back=args.days,
                force=args.force,
                activities=not args.only_biometrics,
                biometrics=not args.only_activities,
            )
            print("  Sync complete.")
        except Exception as e:
            print(f"  Warning: Sync failed: {e}")
            print("  Continuing with cached data...")

    if args.backfill_weight:
        print(f"\n[Backfill] Patching historical weight data for {persona['name']}...")
        garmin = GarminService(
            persona["garmin_email"],
            persona["garmin_password"],
            persona["token_dir"],
            persona["stats_dir"],
        )
        garmin.authenticate()
        garmin.backfill_weight(force=args.force)
        print(f"\n=== Weight backfill complete for {persona['name']} ===")
        return

    if args.backfill_details:
        print(f"\n[Backfill] Fetching activity splits + HR time-series for {persona['name']}...")
        garmin = GarminService(
            persona["garmin_email"],
            persona["garmin_password"],
            persona["token_dir"],
            persona["stats_dir"],
        )
        garmin.authenticate()
        garmin.backfill_activity_details(force=args.force)
        print(f"\n=== Activity details backfill complete for {persona['name']} ===")
        return

    if args.sync_only:
        print(f"\n=== Sync complete for {persona['name']} ===")
        return

    # Step 2: Generate data snapshot (fire-and-forget subprocess — not piped through AI)
    print(f"\n[Step 2] Generating data snapshot...")
    report_cmd = [sys.executable, "-m", "src.report", "--persona", persona_name, "--days", str(args.days)]
    result = subprocess.run(report_cmd, capture_output=False)

    if result.returncode != 0:
        print("  Warning: report generation failed. Check errors above.")
    print(f"\n=== AjCoach: Data ready for {persona['name']} ===")
    print("  Now provide the snapshot to your AI coach with any context (e.g. 'I'm tired today').")


if __name__ == "__main__":
    main()
