---
name: post-workout
description: Review what was actually done vs what was planned in today's session. Fetches today's Hevy workout log via MCP and appends a post-workout summary to today's coaching report.
---

# /post-workout

Review what was actually done vs what was planned.

## Steps

0. **Sync Garmin data first (required):**
   ```
   python coach.py --persona <persona>
   ```
   This generates `personas/<persona>/reports/YYYY-MM-DD_data.md` with recovery metrics (HRV, sleep, RHR, Training Readiness). Post-workout review requires this data snapshot.

1. Read today's coaching report: `personas/<persona>/reports/YYYY-MM-DD_coaching.md`
   - Should include pre-workout recovery snapshot from Step 0
2. Fetch the most recent logged workout from Hevy:
   ```
   python src/hevy_service.py --persona <persona> get-workouts --page 1 --page-size 1
   ```
   - If the most recent workout's `start_time` matches today's date, use it as the actual session data.
   - If nothing logged today, ask the user what was done.
3. Note any user comments about how the session felt

## Review

Compare planned vs actual:
- Which exercises were done? Any skipped or substituted?
- Were planned loads achieved? Higher or lower?
- Was cardio block completed? Duration and average HR?
- How did lower back feel?

## Output

Append a post-workout section to today's coaching report (`YYYY-MM-DD_coaching.md`):

```markdown
---
## Post-Workout Review — [DATE]

### Completed vs Planned
| Exercise | Planned | Actual | Notes |
|---|---|---|---|
| Bench Press | 3×10 @ 82.5kg | 3×8 @ 82.5kg | Form broke down on set 3 |
...

### Cardio
Planned: 25 min Zone 2 | Actual: [X] min | Avg HR: [X] bpm | Zone compliance: [Yes/No]

### Key Takeaways
- [What to carry forward to next session]
- [Any load adjustment for next time]
- [Lower back / injury notes]
```
