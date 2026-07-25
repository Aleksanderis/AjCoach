---
name: review-activity
description: Answer any question about the user's Garmin stats, health trends, or specific activities. Use for ad-hoc questions like "how has my HRV trended this year?", "review my basketball game yesterday", "am I sleeping better than last month?", "what's my resting HR trend?" — anything outside the regular pre/post workout flow.
---

# /review-activity

Answer ad-hoc questions about Garmin data, health metrics, or activity history.

## Data Sources

Read whichever files are relevant to the question:
- `personas/<persona>/stats/garmin_activities.csv` — full activity history
- `personas/<persona>/stats/garmin_biometrics.csv` — HRV, RHR, sleep score, readiness (daily)
- `personas/<persona>/profile.md` — HR zones, sport context, medical notes

Only read what the question actually requires — if it's about sleep, skip activities.

## Answering the Question

Adapt the analysis to what was asked. Common patterns:

**Specific activity review** ("review my basketball game yesterday"):
- Identify the activity by type/date/duration
- HR breakdown using profile.md zones (not Garmin defaults)
- Compare to historical average for that activity type (last 4, 3-month, 12-month)
- Recovery response: HRV/RHR 24–48h after vs baseline

**Metric trend** ("how has my HRV been this year?", "am I sleeping better?"):
- Pull the relevant column across the requested timeframe
- Summarize: current level, trend direction, notable periods (drops, improvements)
- Flag anything clinically relevant (per CLAUDE.md thresholds)

**Comparison** ("was last month harder than this month?"):
- Aggregate load/volume/frequency by period
- Show side-by-side with clear delta

**Open question** ("how am I doing overall?"):
- Brief overview: HRV trend, sleep trend, activity volume, any flags
- 3–5 bullet takeaways

## Format

- Answer in the conversation — no file saved unless user asks
- Use tables when comparing multiple metrics or time periods
- Use profile.md HR zones for any heart rate analysis
- If the activity was recent (≤48h) and next training is today or tomorrow, note the recovery implication
