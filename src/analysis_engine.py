import csv
import os
from typing import List, Optional, Dict, Any
from .models import BiometricEntry


def _csv_int(row: dict, key: str) -> int | None:
    v = row.get(key, 'N/A')
    return int(float(v)) if v != 'N/A' else None

def _csv_float(row: dict, key: str) -> float | None:
    v = row.get(key, 'N/A')
    return float(v) if v != 'N/A' else None


def load_biometric_entries(csv_path: str) -> List[BiometricEntry]:
    entries = []
    if not os.path.exists(csv_path):
        return entries
    _i, _f = _csv_int, _csv_float
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            entries.append(BiometricEntry(
                date=r['Date'],
                hrv=_f(r, 'HRV'),
                sleep_score=_i(r, 'SleepScore'),
                resting_hr=_i(r, 'RestingHR'),
                training_readiness=_i(r, 'TrainingReadiness'),
                active_calories=_i(r, 'ActiveCalories'),
                intensity_minutes=_i(r, 'IntensityMinutes'),
                activity_count=int(float(r['ActivityCount'])),
                steps=_i(r, 'Steps'),
                avg_stress=_i(r, 'AvgStress'),
                body_battery_high=_i(r, 'BodyBatteryHigh'),
                body_battery_low=_i(r, 'BodyBatteryLow'),
                hydration_ml=_i(r, 'HydrationMl'),
                sleep_duration_min=_i(r, 'SleepDurationMin'),
                sleep_deep_min=_i(r, 'SleepDeepMin'),
                sleep_rem_min=_i(r, 'SleepRemMin'),
                sleep_light_min=_i(r, 'SleepLightMin'),
                spo2_avg=_f(r, 'SpO2Avg'),
                breathing_rate=_f(r, 'BreathingRate'),
                weight_kg=_f(r, 'WeightKg'),
            ))
    return entries


def compute_biometric_summary(entries: List[BiometricEntry]) -> Dict[str, Any]:
    """
    Pre-aggregates biometric data for AI consumption.
    Returns computed stats — no traffic light decisions, that's the AI's job.
    """
    if not entries:
        return {}

    # Use the most recent entry that has actual HRV data (today may not have synced yet)
    hrv_entries = [e for e in entries if e.hrv is not None]
    latest_hrv = hrv_entries[-1] if hrv_entries else None

    # HRV stats
    hrv_7d = [e.hrv for e in entries[-8:-1] if e.hrv is not None]
    hrv_today = latest_hrv.hrv if latest_hrv else None
    hrv_7d_avg = round(sum(hrv_7d) / len(hrv_7d), 1) if hrv_7d else None
    hrv_delta_pct = None
    if hrv_today is not None and hrv_7d_avg:
        hrv_delta_pct = round(((hrv_today - hrv_7d_avg) / hrv_7d_avg) * 100, 1)

    # HRV trend: last 5 days
    hrv_5d = [e.hrv for e in entries[-5:] if e.hrv is not None]
    hrv_trend = "unknown"
    if len(hrv_5d) >= 3:
        if hrv_5d[-1] > hrv_5d[0]:
            hrv_trend = "improving"
        elif hrv_5d[-1] < hrv_5d[0]:
            hrv_trend = "declining"
        else:
            hrv_trend = "stable"
    hrv_5d_str = "→".join(str(v) for v in hrv_5d)

    # RHR — use most recent non-null entry
    rhr_entries = [e for e in entries if e.resting_hr is not None]
    rhr_today = rhr_entries[-1].resting_hr if rhr_entries else None
    rhr_values = [e.resting_hr for e in entries[-8:-1] if e.resting_hr is not None]
    rhr_7d_avg = round(sum(rhr_values) / len(rhr_values), 1) if rhr_values else None
    rhr_delta_pct = None
    if rhr_today is not None and rhr_7d_avg:
        rhr_delta_pct = round(((rhr_today - rhr_7d_avg) / rhr_7d_avg) * 100, 1)

    # Readiness — most recent non-null
    readiness_entries = [e for e in entries if e.training_readiness is not None]
    readiness_today = readiness_entries[-1].training_readiness if readiness_entries else None

    # Sleep — most recent non-null
    sleep_values = [e.sleep_score for e in entries if e.sleep_score is not None]
    sleep_today = sleep_values[-1] if sleep_values else None
    sleep_7d_avg = round(sum(sleep_values[-7:]) / len(sleep_values[-7:]), 1) if sleep_values else None
    sleep_data_gap = all(e.sleep_score is None for e in entries[-7:])

    # Label dates for context
    latest_hrv_date = latest_hrv.date if latest_hrv else None
    latest_rhr_date = rhr_entries[-1].date if rhr_entries else None

    return {
        "hrv_today": hrv_today,
        "hrv_today_date": latest_hrv_date,
        "hrv_7d_avg": hrv_7d_avg,
        "hrv_delta_pct": hrv_delta_pct,
        "hrv_trend": hrv_trend,
        "hrv_5d_sequence": hrv_5d_str,
        "rhr_today": rhr_today,
        "rhr_today_date": latest_rhr_date,
        "rhr_7d_avg": rhr_7d_avg,
        "rhr_delta_pct": rhr_delta_pct,
        "readiness_today": readiness_today,
        "sleep_today": sleep_today,
        "sleep_7d_avg": sleep_7d_avg,
        "sleep_data_gap": sleep_data_gap,
    }
