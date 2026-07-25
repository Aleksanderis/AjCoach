---
name: weekly-review
description: Review last week's training and generate next week's session schedule. Run on Sunday or Monday. Writes program/week_YYYY-MM-DD.md and updates Hevy routines if the exercise selection changes for the new week.
---

# /weekly-review

Review last week and set up next week. Run on **Sunday or Monday**.

## Steps

1. Read today's data snapshot: `personas/<persona>/reports/YYYY-MM-DD_data.md`
2. Read `personas/<persona>/profile.md`
3. Read `personas/<persona>/program/current_plan.md`
4. Read last week's coaching reports: `personas/<persona>/reports/` (last 7 days `*_coaching.md`)

## Review Last Week

Assess:
- **Adherence:** How many planned sessions completed? Any missed days?
- **Progression:** Which exercises moved forward? Which stalled?
- **Cardio compliance:** Zone 2 target met? HR in range (116–143 bpm)?
- **Recovery pattern:** HRV/RHR trend — accumulated fatigue or recovered well?
- **Lower back / shoulder:** Any issues flagged during sessions?

## Generate Next Week Plan

Write `personas/<persona>/program/week_YYYY-MM-DD.md` (filename = coming Monday's date):

```markdown
# Training Plan: [Mon date] – [Sun date]
**Phase:** [Phase name] — Week [N] of [total]
**Weekly goal:** [1–3 specific goals based on last week's review]

## Schedule
| Day | Session Type | Focus | Cardio | Notes |
|---|---|---|---|---|
| Monday [date] | Strength + Cardio | Upper Push/Pull | 25 min Zone 2 | ... |
| Tuesday [date] | Rest / Active Recovery | — | — | |
| Wednesday [date] | Strength + Cardio | Lower + Core | 25 min Zone 2 | ... |
| Thursday [date] | Cardio Focus | — | 45 min Zone 2 | |
| Friday [date] | Strength + Cardio | Full Body | 25 min Zone 2 | ... |
| Saturday [date] | Rest | — | — | |
| Sunday [date] | Weekly Review | — | — | |

## Load Notes
[Key adjustments: e.g. "Bench: ready to try 85kg", "KB Deadlift: maintain 40kg, focus form"]

## Cardio Progression
[Target duration this week. Increase if last week's HR response was stable in Zone 2]
```

## Update Hevy if Exercises Change

If the exercise selection for next week differs from what's currently in Hevy (new phase, swap due to stalled progress, injury adjustment):
1. Update `src/setup_hevy.py` with the new exercise definitions.
2. **Routine ID:** Use `routine_id` cached in `src/setup_hevy.py` — skip `get-routines`.
3. **Template ID:** Use `template_id` cached per exercise — skip `search-exercise-templates`. Only run search for exercises with no `template_id` yet, then store the result:
   ```
   python src/hevy_service.py --persona <persona> search-exercise-templates --query "<name>"
   ```
4. Push the updated routine:
   ```
   python src/hevy_service.py --persona <persona> update-routine --id <routine_id> --data '<api_payload>'
   ```
   See `/sync-hevy` skill for the full API payload format and field mapping.
5. State which exercises changed and why.

If the exercises are the same and only loads are changing, **do not update Hevy** — load adjustments happen in the coaching report and the user adjusts weight in the Hevy app directly.
