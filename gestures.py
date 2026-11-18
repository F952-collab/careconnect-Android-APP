"""Gesture / vital-sign classification for the CareConnect wearable.

This is a Python port of the logic that runs on the ESP32 transmitter
(MPU6050 accelerometer + temperature), so it can be tested on a PC.
"""

from dataclasses import dataclass
from typing import Optional

# Raw MPU6050 accelerometer threshold (same default as the firmware).
DEFAULT_THRESHOLD = 4000
FLAT_Y_THRESHOLD = 1000
TEMP_HIGH_C = 38.0


@dataclass(frozen=True)
class Alert:
    code: str        # short code sent over LoRa, e.g. "UR"
    message: str     # text shown to the caregiver
    priority: str    # "emergency" | "attention" | "routine"


ALERTS = {
    "UL": Alert("UL", "NEED FOOD", "routine"),
    "UR": Alert("UR", "CALL NURSE", "attention"),
    "LL": Alert("LL", "NEED MEDICINE", "attention"),
    "LR": Alert("LR", "WASHROOM", "routine"),
    "U": Alert("U", "NEED HELP", "emergency"),
    "TH": Alert("TH", "TEMPERATURE HIGH", "emergency"),
}

PRIORITY_ORDER = {"emergency": 0, "attention": 1, "routine": 2}


def classify_gesture(ax: int, ay: int, threshold: int = DEFAULT_THRESHOLD) -> Optional[Alert]:
    """Map accelerometer X/Y readings to an alert, or None if no gesture."""
    if ax < -threshold and ay > threshold:
        return ALERTS["UL"]
    if ax > threshold and ay > threshold:
        return ALERTS["UR"]
    if ax < -threshold and ay < -threshold:
        return ALERTS["LL"]
    if ax > threshold and ay < -threshold:
        return ALERTS["LR"]
    if ay < -FLAT_Y_THRESHOLD:
        return ALERTS["U"]
    return None


def classify_reading(ax: int, ay: int, temperature: Optional[float] = None,
                     threshold: int = DEFAULT_THRESHOLD) -> Optional[Alert]:
    """High temperature always outranks a gesture."""
    if temperature is not None and temperature >= TEMP_HIGH_C:
        return ALERTS["TH"]
    return classify_gesture(ax, ay, threshold)
