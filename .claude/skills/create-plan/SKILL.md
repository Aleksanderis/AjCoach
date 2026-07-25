---
name: create-plan
description: Create or update the long-term training program, generate the current week's schedule, and populate Hevy routines with the actual exercises. Run when setting new goals, starting a new season, returning from a break, or after a significant injury change.
---

# /create-plan

Create or update the training program and set up Hevy so it's ready to use.

Run when: new season, new goals, major injury/constraint change, returning from a break.

## Steps

1. Read `personas/<persona>/profile.md`
2. Read user's stated goals, schedule, and constraints from the conversation
3. If `program/current_plan.md` exists, read it to understand what's changing

## Generate Program Plan

Write `personas/<persona>/program/current_plan.md`:

```markdown
# Training Program — [Season/Period Name]
**Period:** [Start] – [End]
**Primary goal:** [e.g. Build aerobic base, maintain strength. No basketball.]

## Phase Structure
| Phase | Dates | Focus | Volume | Intensity |
|---|---|---|---|---|
| Base Building | Jun 8 – Jul 5 | Aerobic base + technique | Moderate | Low–Moderate |
| Development | Jul 6 – Aug 2 | Strength progression + endurance | Higher | Moderate |
| ... | | | | |

## Weekly Structure Template
| Day | Session | Duration | Notes |
|---|---|---|---|
| Monday | Strength + Cardio | ~60 min | Upper focus |
| Tuesday | Rest | — | |
| Wednesday | Strength + Cardio | ~60 min | Lower + Core |
| Thursday | Cardio Focus | ~50 min | Zone 2 treadmill |
| Friday | Strength + Cardio | ~60 min | Full Body |
| Sat/Sun | Rest or optional light activity | — | |

## Cardio Protocol
- **Type:** Zone 2 treadmill, 7 km/h
- **Target HR:** 116–143 bpm (athletic calibration — never use Garmin defaults)
- **Weekly target:** ~2 hrs total (building progressively)
- **Progression:** +5 min/week on dedicated cardio day if HR response is stable

## Strength Protocol
- **Frequency:** 3×/week (Mon/Wed/Fri)
- **Warm-up:** 2 superset pairs × 3 rounds (~8–12 min) — see Section 6 of profile
- **Main block:** 7 exercises — compound first, isolation/stabilization last
- **Progression:** +2.5kg when 3×10 completed cleanly. Deload every 4th week.
- **Lower back:** Stabilization exercise mandatory every session (final main exercise)

## Medical Constraints
- Zone 2 strictly enforced (bronchial hyperreactivity — no high-HR cardio)
- No heavy axial load (barbell squats/deadlifts from floor) on Yellow/Red days
- No pull-ups or floor push-ups (right shoulder)
- Basketball (autumn): recovery stressor only — not counted as training volume

## Autumn Transition (when basketball resumes)
[Describe plan for when basketball returns]
```

## Generate This Week's Plan

Write `personas/<persona>/program/week_YYYY-MM-DD.md` (Monday's date) for the current week.

## Populate Hevy Routines

Hevy must reflect the actual plan so the user can train without AI input.

**Exercise definitions, warm-up supersets, sets/reps, and starting weights live in `src/setup_hevy.py` — that is the single source of truth.**

If exercises or weights have changed from what's in `src/setup_hevy.py`, update that file first.

Then push routines via `python src/hevy_service.py`:

1. Read `src/setup_hevy.py` for the routine definitions.
2. **Folder:** `FOLDER_ID` is stored in the file — skip `get-routine-folders`. Only call `create-routine-folder` if adding a brand-new folder:
   ```
   python src/hevy_service.py --persona <persona> create-routine-folder --data '{"routine_folder": {"title": "<name>"}}'
   ```
3. **Template IDs:** Every exercise has a `template_id` cached in `setup_hevy.py` — skip `search-exercise-templates`. Only call it for exercises that have no `template_id` yet (new additions), then store the result back in the file. For custom templates, also add an entry to `src/custom_exercise_templates.md`.
4. **Routine IDs:** Every routine has a `routine_id` cached — skip `get-routines`. Call `update-routine` directly:
   ```
   python src/hevy_service.py --persona <persona> update-routine --id <routine_id> --data '<api_payload>'
   ```
   Only call `create-routine` if `routine_id` is absent (truly new routine):
   ```
   python src/hevy_service.py --persona <persona> create-routine --data '<api_payload>'
   ```
5. Confirm to the user which routines were updated, listing key exercises per routine.

See `/sync-hevy` skill for the full API payload format and field mapping from `setup_hevy.py` → API (template_id → exercise_template_id, duration_s → duration_seconds, etc.).

## Resolving New Exercises

When a new exercise is introduced (no `template_id` in `setup_hevy.py`):

1. Check `src/custom_exercise_templates.md` first — if the exercise is already there, use its `template_id` directly. No API call needed.
2. If not in the registry: run search:
   ```
   python src/hevy_service.py --persona <persona> search-exercise-templates --query "<exercise name>"
   ```
3. If no match: try 1–2 alternative phrasings (e.g. "Deadlift (Kettlebell)" vs "Kettlebell Deadlift", "Band Pull Apart" vs "pull apart").
4. If a standard template is found (`is_custom: false`): use it — better for tracking consistency.
5. If nothing found: create a custom template:
   ```
   python src/hevy_service.py --persona <persona> create-exercise-template --data '<json>'
   ```
   Add it to `src/custom_exercise_templates.md`.
6. Store the resolved `template_id` in `setup_hevy.py` immediately.

**Image/notes on custom templates:** The Hevy API (and hevy-mcp) does not support image upload or notes on exercise templates. If a reference is useful, add it as a comment in `setup_hevy.py` next to the exercise entry — it won't appear in the Hevy app but serves as documentation here.
