---
name: pre-workout
description: Generate today's coaching session plan based on recovery data snapshot and weekly program. Assigns traffic light, determines loads and any adjustments, writes coaching report. Does NOT touch Hevy routines — they are stable and only updated on demand via /weekly-review or explicit request.
---

# /pre-workout

Generate today's coaching session plan.

## Steps

1. **Sync Garmin data first (required):**
   ```
   python coach.py --persona <persona>
   ```
   Then read today's data snapshot: `personas/<persona>/reports/YYYY-MM-DD_data.md` (use today's date). If the sync reports data already cached but fresher data is expected (e.g. user corrected an entry in Garmin Connect), re-run with `--force`.
2. Read `personas/<persona>/profile.md` for full medical/coaching context
3. Note any user-provided context ("I'm tired", "shoulder is sore", etc.)

## Analysis

**Assign traffic light** based on computed recovery metrics in the snapshot:
- HRV delta, trend, RHR delta, readiness, sleep, last high-intensity activity
- Rules: see profile.md Section 6 and CLAUDE.md

**Identify session type** from "Today's planned session" in the snapshot.
- If no week plan exists → warn user and default to Strength (Full Body) conservatively
- Adjust session based on traffic light: Green = full plan, Yellow = reduce load/swap, Red = minimal load + mobility

**Fetch exercise history from Hevy** before determining loads:
- Identify today's routine from `src/setup_hevy.py` using `routine_id` — skip `get-routines`.
- Fetch history only for **loaded exercises** (those with `weight_kg` in `setup_hevy.py`). Skip bodyweight/duration exercises (Bird Dog, Plank, Treadmill, Pallof Press at fixed load) — their prescription doesn't change based on history.
- For each loaded exercise, run:
  ```
  python src/hevy_service.py --persona <persona> get-exercise-history --template-id <template_id>
  ```
  The response is `{"exercise_history": [...]}` where each entry has `sets` with `weight_kg` and `reps`.

**Determine load** based on the retrieved history:
- Last session 3×10 completed cleanly → +2.5kg or progress to 4×10
- Last session was Yellow/Red (reduced) → restore to previous Green load first
- No history → start at 60% estimated 1RM (state assumption explicitly)
- Yellow day → same weight as last session, reduce sets or reps
- Red day → -10–15% load, note any exercise swaps as suggestions only

## Output

Write the coaching report to `personas/<persona>/reports/YYYY-MM-DD_coaching.md`:

```markdown
## Session — [DATE] — [🟢/🟡/🔴] [Status]

### Recovery Summary
[2–3 sentences: what the data shows, why this status]

### Flags
| # | Signal | Value | Threshold | Verdict |
...

### Session Plan (~60 min total)
| # | Exercise | Sets × Reps | Load | Notes |
| 🔥 | Warm-up | 5 min | — | hip circles, leg swings, shoulder rolls |
...
| ❄️ | Cool-down / MFR | 8–10 min | — | hamstrings, hip flexors, thoracic spine |

### Cardio Block
Zone 2 treadmill — 7 km/h — target 116–143 bpm — [X] min

### Reasoning
[Bullet points: load decisions, any recommended swaps if Yellow/Red]
```

**Do NOT modify Hevy routines.** The coaching report is the output — the user follows it during the session and logs sets/reps in Hevy manually. Routines are only updated when the user explicitly asks or during `/weekly-review` if exercises change.
