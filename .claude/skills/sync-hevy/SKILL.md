---
name: sync-hevy
description: Push the current setup_hevy.py routine definitions to Hevy via direct API calls. Run after editing setup_hevy.py — exercises, sets, reps, weights, or notes. Does NOT search or look up IDs; all IDs are cached in the file.
---

# /sync-hevy

Sync `personas/<persona>/setup_hevy.py` → Hevy routines.

Run after any edit to `setup_hevy.py`: exercise swap, sets/reps change, note update, or a **baseline weight change** — a confirmed progression, or a correction to the working weight due to a persistent issue.

**Do NOT run for temporary Yellow/Red-day load reductions** — those are session-specific, tied to today's recovery status, and live in the coaching report only; the persona adjusts weight down in the app for that one session and it bounces back to baseline next time. Confirmed baseline changes are the opposite — sync them the same session the decision is made, don't wait for `/weekly-review` or leave them sitting only in a coaching report.

## Steps

1. Run:
   ```bash
   python src/hevy_service.py --persona <persona> sync-routines
   ```
   This reads `setup_hevy.py` directly, constructs all payloads internally, and pushes every routine. Output is one confirmation line per routine.

   To push a single routine only:
   ```bash
   python src/hevy_service.py --persona <persona> sync-routines --name "Full Body (Fri)"
   ```

2. For exercises with no `template_id` yet (new addition):
   1. Check `src/custom_exercise_templates.md` first — use its ID directly if found.
   2. Otherwise search: `python src/hevy_service.py --persona <persona> search-exercise-templates --query "<name>"`
   3. If nothing found, create: `python src/hevy_service.py --persona <persona> create-exercise-template --data '<json>'`
      - Required fields: `exercise_template_id`, `exercise_type`, `muscle_group`, `equipment_category`
      - Valid muscle_group values: `abdominals shoulders biceps triceps forearms quadriceps hamstrings calves glutes abductors adductors lats upper_back traps lower_back chest cardio neck full_body other`
      - Valid equipment_category: `none barbell dumbbell kettlebell machine plate resistance_band suspension other`
   4. Add the result to `src/custom_exercise_templates.md` and store `template_id` in `setup_hevy.py`.
   5. Then run `sync-routines`.

3. Confirm which routines were updated and note any notable changes to the user.

## superset_id in setup_hevy.py

Warm-up exercises use list-of-lists — each inner list is one superset pair (assigned IDs automatically by `sync-routines`).

Main block exercises can include `"superset_id": <int>` to group them as a superset. Use any consistent integer — exercises sharing the same integer get linked. Example: `"superset_id": 4` on both Hammer Curl and Triceps Pushdown pairs them.

