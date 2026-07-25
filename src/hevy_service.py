"""
hevy_service.py — Direct Hevy API CLI

Usage:
  python src/hevy_service.py --persona <name> <command> [options]

Loads HEVY_API_KEY from personas/<name>/.env
Prints JSON to stdout. Exits non-zero on API error.

Commands:
  get-workouts           [--page N] [--page-size N]
  get-workout            --id WORKOUT_ID
  get-workout-count
  get-routines           [--page N] [--page-size N]
  get-routine            --id ROUTINE_ID
  create-routine         --data JSON
  update-routine         --id ROUTINE_ID --data JSON
  get-exercise-templates [--page N] [--page-size N]
  get-exercise-template  --id TEMPLATE_ID
  search-exercise-templates --query TEXT
  create-exercise-template  --data JSON
  get-exercise-history   --template-id TEMPLATE_ID [--page-size N] [--start-date ISO] [--end-date ISO]
  get-routine-folders    [--page N]
  create-routine-folder  --data JSON
  sync-routines          [--name "Routine Name"]  (reads setup_hevy.py and pushes all routines)

For large --data payloads, write JSON to a file and pass --data @/path/to/file.json
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error

BASE_URL = "https://api.hevyapp.com/v1"


def _load_api_key(persona: str) -> str:
    env_path = os.path.join("personas", persona, ".env")
    if not os.path.exists(env_path):
        sys.exit(f"ERROR: {env_path} not found")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("HEVY_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit(f"ERROR: HEVY_API_KEY not found in {env_path}")


def _load_data(data_arg: str) -> dict:
    if data_arg.startswith("@"):
        with open(data_arg[1:]) as f:
            raw = f.read()
    else:
        raw = data_arg
    return json.loads(raw)


def _request(method: str, path: str, api_key: str, params: dict = None, body: dict = None):
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("api-key", api_key)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
            if not content:
                return {}
            text = content.decode('utf-8').strip()
            if not text:
                return {}
            return json.JSONDecoder().raw_decode(text)[0]
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        sys.exit(f"ERROR: HTTP {e.code} {e.reason} — {body_text}")


def _build_routine_payload(routine: dict) -> dict:
    """Translate a setup_hevy.py routine dict into a Hevy API payload."""
    exercises = []
    superset_counter = 0

    # Warm-up: list of lists (each inner list = one superset pair)
    for group in routine.get("warmup", []):
        superset_counter += 1
        sid = superset_counter
        for ex in group:
            sets = []
            for _ in range(ex.get("sets", 1)):
                if "duration_s" in ex:
                    sets.append({"type": "warmup", "weight_kg": None, "reps": 1,
                                 "duration_seconds": ex["duration_s"],
                                 "rep_range": {"start": 1, "end": 1}})
                else:
                    sets.append({"type": "warmup", "weight_kg": ex.get("weight_kg"),
                                 "reps": ex.get("reps"), "duration_seconds": None,
                                 "rep_range": {"start": ex.get("reps", 1), "end": ex.get("reps", 1)}})
            exercises.append({
                "exercise_template_id": ex["template_id"],
                "superset_id": sid,
                "notes": ex.get("notes"),
                "sets": sets,
            })

    # Main block
    # Collect superset_ids already used in warmup so main block IDs don't collide
    main_superset_map = {}  # setup_hevy superset_id -> API superset_id
    for ex in routine.get("exercises", []):
        raw_sid = ex.get("superset_id")
        if raw_sid is not None and raw_sid not in main_superset_map:
            superset_counter += 1
            main_superset_map[raw_sid] = superset_counter

        api_sid = main_superset_map.get(raw_sid) if raw_sid is not None else None
        sets = []
        for _ in range(ex.get("sets", 1)):
            if "duration_s" in ex:
                sets.append({"type": "normal", "weight_kg": None, "reps": 1,
                             "duration_seconds": ex["duration_s"],
                             "rep_range": {"start": 1, "end": 1}})
            else:
                reps = ex.get("reps", 1)
                sets.append({"type": "normal", "weight_kg": ex.get("weight_kg"),
                             "reps": reps, "duration_seconds": None,
                             "rep_range": {"start": reps, "end": reps}})
        exercises.append({
            "exercise_template_id": ex["template_id"],
            "superset_id": api_sid,
            "notes": ex.get("notes"),
            "sets": sets,
        })

    return {"routine": {"title": routine["name"], "notes": None, "exercises": exercises}}


def _sync_routines(persona: str, api_key: str, names: list = None):
    """Push routines from setup_hevy.py to Hevy. Optionally filter by name."""
    from setup_hevy import load_persona_routines
    routines, _ = load_persona_routines(persona)
    for routine in routines:
        if names and routine["name"] not in names:
            continue
        payload = _build_routine_payload(routine)
        _request("PUT", f"/routines/{routine['routine_id']}", api_key, body=payload)
        print(f"OK: updated routine '{routine['name']}'")


def main():
    parser = argparse.ArgumentParser(description="Hevy API CLI")
    parser.add_argument("--persona", required=True, help="Persona name (loads key from personas/<name>/.env)")
    parser.add_argument("command", help="API command to run")
    parser.add_argument("--id", help="Resource ID")
    parser.add_argument("--template-id", dest="template_id", help="Exercise template ID")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=5, dest="page_size")
    parser.add_argument("--data", help="JSON body or @filepath")
    parser.add_argument("--query", help="Search query text")
    parser.add_argument("--start-date", dest="start_date", help="ISO 8601 start date for history")
    parser.add_argument("--end-date", dest="end_date", help="ISO 8601 end date for history")
    parser.add_argument("--quiet", "-q", action="store_true", help="Print only a short confirmation for write commands")
    parser.add_argument("--name", help="Routine name filter for sync-routines")
    args = parser.parse_args()

    api_key = _load_api_key(args.persona)
    cmd = args.command

    if cmd == "get-workouts":
        result = _request("GET", "/workouts", api_key, {"page": args.page, "pageSize": min(args.page_size, 10)})

    elif cmd == "get-workout":
        if not args.id:
            sys.exit("ERROR: --id required")
        result = _request("GET", f"/workouts/{args.id}", api_key)

    elif cmd == "get-workout-count":
        result = _request("GET", "/workouts/count", api_key)

    elif cmd == "get-routines":
        result = _request("GET", "/routines", api_key, {"page": args.page, "pageSize": min(args.page_size, 10)})

    elif cmd == "get-routine":
        if not args.id:
            sys.exit("ERROR: --id required")
        result = _request("GET", f"/routines/{args.id}", api_key)

    elif cmd == "create-routine":
        if not args.data:
            sys.exit("ERROR: --data required")
        result = _request("POST", "/routines", api_key, body=_load_data(args.data))
        if args.quiet:
            routines = result.get("routine", [{}])
            title = routines[0].get("title", "?") if routines else "?"
            rid = routines[0].get("id", "?") if routines else "?"
            print(f"OK: created routine '{title}' id={rid}")
            return

    elif cmd == "update-routine":
        if not args.id or not args.data:
            sys.exit("ERROR: --id and --data required")
        result = _request("PUT", f"/routines/{args.id}", api_key, body=_load_data(args.data))
        if args.quiet:
            routines = result.get("routine", [{}])
            title = routines[0].get("title", args.id) if routines else args.id
            print(f"OK: updated routine '{title}'")
            return

    elif cmd == "get-exercise-templates":
        result = _request("GET", "/exercise_templates", api_key, {"page": args.page, "pageSize": min(args.page_size, 100)})

    elif cmd == "get-exercise-template":
        if not args.id:
            sys.exit("ERROR: --id required")
        result = _request("GET", f"/exercise_templates/{args.id}", api_key)

    elif cmd == "search-exercise-templates":
        if not args.query:
            sys.exit("ERROR: --query required")
        query_lower = args.query.lower()
        matches = []
        page = 1
        while True:
            resp = _request("GET", "/exercise_templates", api_key, {"page": page, "pageSize": 100})
            for t in resp.get("exercise_templates", []):
                if query_lower in t.get("title", "").lower():
                    matches.append(t)
            if page >= resp.get("page_count", 1):
                break
            page += 1
        result = {"exercise_templates": matches}

    elif cmd == "create-exercise-template":
        if not args.data:
            sys.exit("ERROR: --data required")
        result = _request("POST", "/exercise_templates", api_key, body=_load_data(args.data))
        if args.quiet:
            ex = result.get("exercise_template", {})
            print(f"OK: created exercise template '{ex.get('title', '?')}' id={ex.get('id', '?')}")
            return

    elif cmd == "get-exercise-history":
        if not args.template_id:
            sys.exit("ERROR: --template-id required")
        params = {}
        if args.start_date:
            params["start_date"] = args.start_date
        if args.end_date:
            params["end_date"] = args.end_date
        result = _request("GET", f"/exercise_history/{args.template_id}", api_key, params or None)

    elif cmd == "get-routine-folders":
        result = _request("GET", "/routine_folders", api_key, {"page": args.page, "pageSize": min(args.page_size, 10)})

    elif cmd == "create-routine-folder":
        if not args.data:
            sys.exit("ERROR: --data required")
        result = _request("POST", "/routine_folders", api_key, body=_load_data(args.data))

    elif cmd == "sync-routines":
        names = [args.name] if args.name else None
        _sync_routines(args.persona, api_key, names)
        return

    else:
        sys.exit(f"ERROR: Unknown command '{cmd}'. Run with --help for usage.")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
