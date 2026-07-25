from dataclasses import dataclass
from typing import List, Optional

@dataclass
class BiometricEntry:
    date: str
    hrv: Optional[float]
    sleep_score: Optional[int]
    resting_hr: Optional[int]
    training_readiness: Optional[int]
    active_calories: Optional[int]
    intensity_minutes: Optional[int]
    activity_count: int
    steps: Optional[int] = None
    avg_stress: Optional[int] = None
    body_battery_high: Optional[int] = None  # highest of day (morning charge)
    body_battery_low: Optional[int] = None   # lowest of day (peak depletion)
    hydration_ml: Optional[int] = None
    sleep_duration_min: Optional[int] = None
    sleep_deep_min: Optional[int] = None
    sleep_rem_min: Optional[int] = None
    sleep_light_min: Optional[int] = None
    spo2_avg: Optional[float] = None         # avg blood oxygen %
    breathing_rate: Optional[float] = None   # avg breaths/min
    weight_kg: Optional[float] = None        # body weight from Garmin scale

@dataclass
class ActivityEntry:
    id: str
    date: str
    start_time: str
    name: str
    type: str
    duration_secs: int
    avg_hr: Optional[int]
    max_hr: Optional[int]
    zones_mins: List[float] # [Z1, Z2, Z3, Z4, Z5]

@dataclass
class UserFeedback:
    date: str
    text: str
    pain_level: int # 0-10

@dataclass
class CoachingRecommendation:
    recommendation: str # "Full Workout", "Moderate", "Deload"
    flags: List[str]
    latest_metrics: BiometricEntry
    feedback: Optional[UserFeedback] = None
