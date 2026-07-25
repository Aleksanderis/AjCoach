import os
import sys
import csv
import json
import datetime
import time
from typing import List, Tuple, Optional
from garminconnect import Garmin
from .models import BiometricEntry, ActivityEntry
from .analysis_engine import _csv_int, _csv_float

class GarminService:
    def __init__(self, email: str, password: str, token_dir: str, stats_dir: str):
        self.client = Garmin(email or "", password or "")
        self.token_dir = token_dir
        self.stats_dir = stats_dir
        self.biometrics_csv = os.path.join(stats_dir, "garmin_biometrics.csv")
        self.activities_csv = os.path.join(stats_dir, "garmin_activities.csv")
        self._authenticated = False

    def authenticate(self):
        print(f"Authenticating with Garmin (Tokens: {self.token_dir})...")
        try:
            self.client.login(self.token_dir)
            self._authenticated = True
            print("Garmin authentication successful.")
        except Exception as e:
            raise ConnectionError(f"Garmin login failed: {e}")

    def sync(self, days_back: int = 7, force: bool = False, activities: bool = True, biometrics: bool = True):
        if not self._authenticated:
            self.authenticate()

        os.makedirs(self.stats_dir, exist_ok=True)
        today = datetime.date.today()
        start_date = today - datetime.timedelta(days=days_back-1)

        # Load existing data to avoid redundant API calls
        existing_biometrics = self._load_local_biometrics()
        existing_activity_ids = self._load_local_activity_ids()

        # Don't go earlier than the device start date — avoids fetching pre-Garmin dates
        garmin_start_env = os.environ.get('GARMIN_START_DATE')
        if garmin_start_env:
            device_start = datetime.date.fromisoformat(garmin_start_env)
            if start_date < device_start:
                start_date = device_start

        print(f"Syncing Garmin data from {start_date} to {today}...")
        
        ACTIVITY_FLUSH_EVERY = 20
        BIOMETRIC_FLUSH_EVERY = 30

        # 1. Bulk Activity Sync
        all_activities = []
        activities_by_date = {}

        if activities:
            all_activities = self.client.get_activities_by_date(start_date.isoformat(), today.isoformat())
            activity_batch = []

            for act in all_activities:
                date_str = act.get('startTimeLocal', '')[:10]
                if date_str not in activities_by_date:
                    activities_by_date[date_str] = []
                activities_by_date[date_str].append(act)

                act_id = str(act.get('activityId'))
                if act_id not in existing_activity_ids or force:
                    print(f"  - New activity: {act.get('activityName')} ({act_id})")
                    zones = self._fetch_hr_zones(act_id)
                    activity_batch.append(ActivityEntry(
                        id=act_id, date=date_str,
                        start_time=act.get('startTimeLocal', '')[:19],
                        name=act.get('activityName'),
                        type=(act.get('activityType') or {}).get('typeKey'),
                        duration_secs=act.get('duration'),
                        avg_hr=act.get('averageHR'), max_hr=act.get('maxHR'),
                        zones_mins=zones
                    ))
                    existing_activity_ids.add(act_id)
                    time.sleep(0.5)

                    if len(activity_batch) >= ACTIVITY_FLUSH_EVERY:
                        self._save_local_activities(activity_batch)
                        print(f"  [checkpoint] Flushed {len(activity_batch)} activities to disk.")
                        activity_batch = []

            if activity_batch:
                self._save_local_activities(activity_batch)

            # Fetch granular details (splits + HR time-series) for activities not yet cached
            for act in all_activities:
                act_id = str(act.get('activityId'))
                if self._fetch_and_save_activity_details(act_id):
                    time.sleep(0.5)  # only rate-limit when we actually hit the API
        else:
            # Still need activities_by_date for accurate activity_count in biometrics
            if biometrics:
                all_activities = self.client.get_activities_by_date(start_date.isoformat(), today.isoformat())
                for act in all_activities:
                    date_str = act.get('startTimeLocal', '')[:10]
                    if date_str not in activities_by_date:
                        activities_by_date[date_str] = []
                    activities_by_date[date_str].append(act)

        # 2. Daily Biometrics Sync
        if not biometrics:
            return

        current_date = start_date
        days_since_flush = 0
        while current_date <= today:
            date_str = current_date.isoformat()
            is_recent = (today - current_date).days <= 3

            if date_str in existing_biometrics and not force and not is_recent:
                existing_biometrics[date_str].activity_count = len(activities_by_date.get(date_str, []))
            else:
                print(f"  - Fetching biometrics for {date_str}")
                entry = self._fetch_daily_biometrics(date_str, len(activities_by_date.get(date_str, [])))
                existing_biometrics[date_str] = entry
                days_since_flush += 1
                time.sleep(0.5)

            if days_since_flush >= BIOMETRIC_FLUSH_EVERY:
                self._save_local_biometrics(existing_biometrics)
                print(f"  [checkpoint] Flushed biometrics to disk (up to {date_str}).")
                days_since_flush = 0

            current_date += datetime.timedelta(days=1)

        self._save_local_biometrics(existing_biometrics)

    def _fetch_hr_zones(self, activity_id: str) -> List[float]:
        zones = [0.0] * 5
        try:
            hr_zones = self.client.get_activity_hr_in_timezones(activity_id)
            for zone_info in hr_zones:
                idx = zone_info.get('zoneNumber', 0)
                if 1 <= idx <= 5:
                    zones[idx-1] = round(zone_info.get('secsInZone', 0) / 60, 2)
        except Exception: pass
        return zones

    def _activity_details_path(self, activity_id: str) -> str:
        return os.path.join(self.stats_dir, "activity_details", f"{activity_id}.json")

    def _fetch_and_save_activity_details(self, activity_id: str) -> bool:
        """Fetch lap splits and HR time-series for an activity, save to JSON. Skips if already cached."""
        dest = self._activity_details_path(activity_id)
        if os.path.exists(dest):
            return False

        os.makedirs(os.path.dirname(dest), exist_ok=True)
        result: dict = {"activity_id": activity_id, "splits": [], "hr_timeseries": []}

        try:
            splits_data = self.client.get_activity_splits(activity_id)
            laps = splits_data.get("lapDTOs") or splits_data.get("laps") or []
            if isinstance(laps, list):
                for i, lap in enumerate(laps):
                    result["splits"].append({
                        "lap": i,
                        "duration_s": round(float(lap.get("duration") or 0), 1),
                        "distance_m": round(float(lap.get("distance") or 0), 1) if lap.get("distance") else None,
                        "avg_hr": lap.get("averageHR"),
                        "max_hr": lap.get("maxHR"),
                        "intensity": lap.get("intensityType"),
                    })
        except Exception as ex:
            print(f"  [details] splits failed {activity_id}: {ex}", file=sys.stderr)

        time.sleep(0.3)

        try:
            detail_data = self.client.get_activity_details(activity_id, maxchart=2000)
            descriptors = detail_data.get("metricDescriptors", [])
            metrics = detail_data.get("activityDetailMetrics", [])

            hr_idx: Optional[int] = None
            ts_idx: Optional[int] = None
            for d in descriptors:
                key = d.get("key", "")
                idx = d.get("metricsIndex")
                if idx is None:
                    continue
                if "heartRate" in key or key == "directHeartRate":
                    hr_idx = idx
                if "Timestamp" in key or key == "directTimestamp":
                    ts_idx = idx

            if hr_idx is not None and metrics:
                first_ts = None
                if ts_idx is not None:
                    for m in metrics:
                        v = m.get("metrics", [])
                        if ts_idx < len(v) and v[ts_idx] is not None:
                            first_ts = v[ts_idx]
                            break

                for m in metrics:
                    vals = m.get("metrics", [])
                    if hr_idx >= len(vals) or vals[hr_idx] is None:
                        continue
                    hr = int(vals[hr_idx])
                    offset: Optional[int] = None
                    if ts_idx is not None and ts_idx < len(vals) and first_ts and vals[ts_idx] is not None:
                        offset = round((vals[ts_idx] - first_ts) / 1000)
                    result["hr_timeseries"].append([offset, hr])
        except Exception as ex:
            print(f"  [details] timeseries failed {activity_id}: {ex}", file=sys.stderr)

        if result["splits"] or result["hr_timeseries"]:
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(result, f)
            print(f"  [details] {activity_id}: {len(result['splits'])} splits, {len(result['hr_timeseries'])} HR pts")
            return True

        return False

    def backfill_activity_details(self, force: bool = False):
        """Fetch details for all activities in the CSV that don't have a cached file yet."""
        if not self._authenticated:
            self.authenticate()

        activity_ids = sorted(self._load_local_activity_ids())
        if not activity_ids:
            print("  No activities to backfill.")
            return

        missing = [aid for aid in activity_ids
                   if force or not os.path.exists(self._activity_details_path(aid))]

        if not missing:
            print(f"  All {len(activity_ids)} activities already have details. Use --force to re-fetch.")
            return

        print(f"  Fetching details for {len(missing)}/{len(activity_ids)} activities...")
        fetched = 0
        for act_id in missing:
            if force:
                dest = self._activity_details_path(act_id)
                if os.path.exists(dest):
                    os.remove(dest)
            if self._fetch_and_save_activity_details(act_id):
                fetched += 1
            time.sleep(0.5)

        print(f"  Backfill complete — {fetched}/{len(missing)} saved.")

    def _fetch_daily_biometrics(self, date_str: str, act_count: int) -> BiometricEntry:
        try:
            sleep = self.client.get_sleep_data(date_str)
            dto = sleep.get('dailySleepDTO', {})
            sleep_score = (
                dto.get('sleepScores', {}).get('overall', {}).get('value')
                or dto.get('sleepScore')
                or sleep.get('sleepScores', {}).get('overall', {}).get('value')
                or sleep.get('sleepScore')
            )
            if sleep_score is None:
                available_keys = list(dto.keys()) + [f"[top]{k}" for k in sleep.keys()]
                print(f"  [sleep debug] {date_str}: score not found. DTO keys: {available_keys[:20]}", file=sys.stderr)
            def _secs_to_min(v): return round(v / 60) if v is not None else None
            sleep_duration_min = _secs_to_min(dto.get('sleepTimeSeconds') or sleep.get('sleepTimeSeconds'))
            sleep_deep_min = _secs_to_min(dto.get('deepSleepSeconds') or sleep.get('deepSleepSeconds'))
            sleep_rem_min = _secs_to_min(dto.get('remSleepSeconds') or sleep.get('remSleepSeconds'))
            sleep_light_min = _secs_to_min(dto.get('lightSleepSeconds') or sleep.get('lightSleepSeconds'))
        except Exception as ex:
            print(f"  [sleep debug] {date_str}: exception — {ex}", file=sys.stderr)
            sleep_score = sleep_duration_min = sleep_deep_min = sleep_rem_min = sleep_light_min = None
        
        try:
            hrv_data = self.client.get_hrv_data(date_str)
            hrv = hrv_data.get('hrvSummary', {}).get('lastNightAvg')
        except Exception: hrv = None

        try:
            readiness = self.client.get_training_readiness(date_str)
            readiness_score = readiness[0].get('score') if readiness else None
        except Exception: readiness_score = None

        try:
            stats = self.client.get_stats(date_str)
            rhr = stats.get('restingHeartRate')
            cals = stats.get('activeKilocalories') or stats.get('activeCalories')
            mod_mins = stats.get('moderateIntensityMinutes')
            vig_mins = stats.get('vigorousIntensityMinutes')
            if mod_mins is not None or vig_mins is not None:
                imin = (mod_mins or 0) + (vig_mins or 0)
            else:
                imin = stats.get('totalIntensityMinutes')
            steps = stats.get('totalSteps')
            avg_stress = stats.get('averageStressLevel')
            body_battery_high = stats.get('bodyBatteryHighestValue')
            body_battery_low = stats.get('bodyBatteryLowestValue')
        except Exception: rhr = cals = imin = steps = avg_stress = body_battery_high = body_battery_low = None

        try:
            hydration = self.client.get_hydration_data(date_str)
            hydration_ml = hydration.get('totalIntakeInMl') or hydration.get('valueInML')
        except Exception: hydration_ml = None

        try:
            spo2 = self.client.get_spo2_data(date_str)
            spo2_avg = spo2.get('averageSpO2') or (spo2.get('continuousReadingDTOList') or [{}])[0].get('spO2Reading') if spo2 else None
        except Exception: spo2_avg = None

        try:
            resp = self.client.get_respiration_data(date_str)
            breathing_rate = resp.get('avgWakingRespirationValue') or resp.get('lowestRespirationValue')
        except Exception: breathing_rate = None

        try:
            body_comp = self.client.get_body_composition(date_str, date_str)
            weight_g = None
            for entry in (body_comp.get('dateWeightList') or []):
                if entry.get('calendarDate') == date_str:
                    weight_g = entry.get('weight')
                    break
            if weight_g is None:
                avg = (body_comp or {}).get('totalAverage') or {}
                weight_g = avg.get('weight')
            weight_kg = round(weight_g / 1000, 1) if weight_g is not None else None
        except Exception: weight_kg = None

        def _i(v): return int(float(v)) if v is not None else None
        def _f(v): return round(float(v), 1) if v is not None else None

        return BiometricEntry(
            date=date_str,
            hrv=_f(hrv),
            sleep_score=_i(sleep_score),
            resting_hr=_i(rhr),
            training_readiness=_i(readiness_score),
            active_calories=_i(cals),
            intensity_minutes=_i(imin),
            activity_count=act_count,
            steps=_i(steps),
            avg_stress=_i(avg_stress),
            body_battery_high=_i(body_battery_high),
            body_battery_low=_i(body_battery_low),
            hydration_ml=_i(hydration_ml),
            sleep_duration_min=sleep_duration_min,
            sleep_deep_min=sleep_deep_min,
            sleep_rem_min=sleep_rem_min,
            sleep_light_min=sleep_light_min,
            spo2_avg=_f(spo2_avg),
            breathing_rate=_f(breathing_rate),
            weight_kg=weight_kg,
        )

    def _load_local_biometrics(self) -> dict:
        data = {}
        if not os.path.exists(self.biometrics_csv): return data
        with open(self.biometrics_csv, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                data[r['Date']] = BiometricEntry(
                    date=r['Date'],
                    hrv=_csv_float(r, 'HRV'),
                    sleep_score=_csv_int(r, 'SleepScore'),
                    resting_hr=_csv_int(r, 'RestingHR'),
                    training_readiness=_csv_int(r, 'TrainingReadiness'),
                    active_calories=_csv_int(r, 'ActiveCalories'),
                    intensity_minutes=_csv_int(r, 'IntensityMinutes'),
                    activity_count=int(float(r['ActivityCount'])),
                    steps=_csv_int(r, 'Steps'),
                    avg_stress=_csv_int(r, 'AvgStress'),
                    body_battery_high=_csv_int(r, 'BodyBatteryHigh'),
                    body_battery_low=_csv_int(r, 'BodyBatteryLow'),
                    hydration_ml=_csv_int(r, 'HydrationMl'),
                    sleep_duration_min=_csv_int(r, 'SleepDurationMin'),
                    sleep_deep_min=_csv_int(r, 'SleepDeepMin'),
                    sleep_rem_min=_csv_int(r, 'SleepRemMin'),
                    sleep_light_min=_csv_int(r, 'SleepLightMin'),
                    spo2_avg=_csv_float(r, 'SpO2Avg'),
                    breathing_rate=_csv_float(r, 'BreathingRate'),
                    weight_kg=_csv_float(r, 'WeightKg'),
                )
        return data

    def _load_local_activity_ids(self) -> set:
        ids = set()
        if not os.path.exists(self.activities_csv): return ids
        with open(self.activities_csv, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                ids.add(r['ActivityID'])
        return ids

    def _save_local_biometrics(self, data: dict):
        fieldnames = [
            'Date', 'HRV', 'SleepScore', 'RestingHR', 'TrainingReadiness',
            'ActiveCalories', 'IntensityMinutes', 'ActivityCount',
            'Steps', 'AvgStress', 'BodyBatteryHigh', 'BodyBatteryLow',
            'HydrationMl', 'SleepDurationMin', 'SleepDeepMin', 'SleepRemMin',
            'SleepLightMin', 'SpO2Avg', 'BreathingRate', 'WeightKg',
        ]
        def _v(val): return val if val is not None else 'N/A'

        with open(self.biometrics_csv, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for d in sorted(data.keys()):
                e = data[d]
                biometric_fields = [
                    e.hrv, e.sleep_score, e.resting_hr, e.training_readiness,
                    e.active_calories, e.intensity_minutes, e.steps, e.avg_stress,
                    e.body_battery_high, e.body_battery_low, e.hydration_ml,
                    e.sleep_duration_min, e.sleep_deep_min, e.sleep_rem_min,
                    e.sleep_light_min, e.spo2_avg, e.breathing_rate,
                ]
                if all(v is None for v in biometric_fields) and e.activity_count == 0:
                    continue
                writer.writerow({
                    'Date': e.date,
                    'HRV': _v(e.hrv),
                    'SleepScore': _v(e.sleep_score),
                    'RestingHR': _v(e.resting_hr),
                    'TrainingReadiness': _v(e.training_readiness),
                    'ActiveCalories': _v(e.active_calories),
                    'IntensityMinutes': _v(e.intensity_minutes),
                    'ActivityCount': e.activity_count,
                    'Steps': _v(e.steps),
                    'AvgStress': _v(e.avg_stress),
                    'BodyBatteryHigh': _v(e.body_battery_high),
                    'BodyBatteryLow': _v(e.body_battery_low),
                    'HydrationMl': _v(e.hydration_ml),
                    'SleepDurationMin': _v(e.sleep_duration_min),
                    'SleepDeepMin': _v(e.sleep_deep_min),
                    'SleepRemMin': _v(e.sleep_rem_min),
                    'SleepLightMin': _v(e.sleep_light_min),
                    'SpO2Avg': _v(e.spo2_avg),
                    'BreathingRate': _v(e.breathing_rate),
                    'WeightKg': _v(e.weight_kg),
                })

    def backfill_weight(self, force: bool = False):
        """Fetch body composition for all dates missing WeightKg in one API call."""
        if not self._authenticated:
            self.authenticate()

        data = self._load_local_biometrics()
        if not data:
            print("  No existing biometrics data to backfill.")
            return

        if force:
            target_dates = sorted(data.keys())
        else:
            target_dates = sorted(d for d, e in data.items() if e.weight_kg is None)

        if not target_dates:
            print("  All dates already have weight data. Use --force to re-fetch.")
            return

        start_date = target_dates[0]
        end_date = target_dates[-1]
        print(f"  Fetching body composition from {start_date} to {end_date}...")

        try:
            body_comp = self.client.get_body_composition(start_date, end_date)
            weight_by_date = {}
            for entry in (body_comp.get('dateWeightList') or []):
                cal_date = entry.get('calendarDate')
                weight_g = entry.get('weight')
                if cal_date and weight_g is not None:
                    weight_by_date[cal_date] = round(weight_g / 1000, 1)
        except Exception as ex:
            print(f"  Error fetching body composition: {ex}")
            return

        updated = 0
        for date_str in target_dates:
            if date_str in weight_by_date:
                data[date_str].weight_kg = weight_by_date[date_str]
                updated += 1

        self._save_local_biometrics(data)
        print(f"  Backfill complete — {updated}/{len(target_dates)} dates updated with weight data.")

    def _load_local_activities(self) -> dict:
        data = {}
        if not os.path.exists(self.activities_csv): return data
        def _v(r, k): return r[k] if r.get(k, '') != '' else None
        with open(self.activities_csv, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                aid = r['ActivityID']
                # Detect legacy rows where StartTime was incorrectly written as the activity name
                raw_st = r.get('StartTime', '')
                start_time = raw_st if raw_st and raw_st[0].isdigit() else ''
                data[aid] = ActivityEntry(
                    id=aid, date=r['Date'], start_time=start_time, name=r['Name'],
                    type=r.get('Type', ''),
                    duration_secs=int(float(r['Duration'])) if r.get('Duration') else 0,
                    avg_hr=int(float(r['AvgHR'])) if r.get('AvgHR') else None,
                    max_hr=int(float(r['MaxHR'])) if r.get('MaxHR') else None,
                    zones_mins=[
                        float(r.get('Zone1_Mins') or 0), float(r.get('Zone2_Mins') or 0),
                        float(r.get('Zone3_Mins') or 0), float(r.get('Zone4_Mins') or 0),
                        float(r.get('Zone5_Mins') or 0),
                    ],
                )
        return data

    def _save_local_activities(self, new_activities: List[ActivityEntry]):
        if not new_activities: return
        existing = self._load_local_activities()
        for a in new_activities:
            existing[a.id] = a
        fieldnames = ['ActivityID', 'Date', 'StartTime', 'Name', 'Type', 'Duration', 'Distance', 'AvgHR', 'MaxHR', 'Calories', 'Zone1_Mins', 'Zone2_Mins', 'Zone3_Mins', 'Zone4_Mins', 'Zone5_Mins']
        with open(self.activities_csv, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for a in sorted(existing.values(), key=lambda x: (x.date, x.start_time), reverse=True):
                writer.writerow({
                    'ActivityID': a.id, 'Date': a.date, 'StartTime': a.start_time,
                    'Name': a.name, 'Type': a.type,
                    'Duration': a.duration_secs, 'Distance': '0',
                    'AvgHR': a.avg_hr if a.avg_hr is not None else '',
                    'MaxHR': a.max_hr if a.max_hr is not None else '',
                    'Calories': '0',
                    'Zone1_Mins': a.zones_mins[0], 'Zone2_Mins': a.zones_mins[1],
                    'Zone3_Mins': a.zones_mins[2], 'Zone4_Mins': a.zones_mins[3],
                    'Zone5_Mins': a.zones_mins[4],
                })


def load_activity_details(stats_dir: str, activity_id: str) -> Optional[dict]:
    """Load cached activity details (splits + HR time-series) for a given activity ID."""
    path = os.path.join(stats_dir, "activity_details", f"{activity_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
