"""Simulates the ESP32 wearable sending readings to the CareConnect server.

Usage:
    python app.py                     # terminal 1: start the server
    python simulator.py               # terminal 2: send 15 random readings
    python simulator.py --count 30 --interval 0.5
"""

import argparse
import json
import random
import time
import urllib.error
import urllib.request

# (accel_x, accel_y) values that trigger each gesture, plus a resting reading.
GESTURES = {
    "upper_left": (-5000, 5000),
    "upper_right": (5000, 5000),
    "lower_left": (-5000, -5000),
    "lower_right": (5000, -5000),
    "tilt_help": (0, -2000),
    "rest": (100, 200),
}


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--server", default="http://127.0.0.1:5000")
    p.add_argument("--count", type=int, default=15)
    p.add_argument("--interval", type=float, default=1.0, help="seconds between readings")
    p.add_argument("--seed", type=int, default=None)
    args = p.parse_args()
    rng = random.Random(args.seed)

    try:
        patient = post(f"{args.server}/api/patients", {"name": "Demo Patient", "bed_number": rng.randint(100, 999)})
    except urllib.error.URLError as e:
        raise SystemExit(f"Could not reach server at {args.server}: {e}. Start it with: python app.py")

    print(f"Simulating patient {patient['name']} (bed {patient['bed_number']})")
    for i in range(1, args.count + 1):
        name = rng.choice(list(GESTURES))
        ax, ay = GESTURES[name]
        temp = round(rng.uniform(36.2, 39.2), 1)
        result = post(f"{args.server}/api/readings",
                      {"patient_id": patient["id"], "accel_x": ax, "accel_y": ay, "temperature": temp})
        label = result.get("message") or "normal"
        print(f"[{i:02d}] gesture={name:<11} temp={temp:>4}C -> {label}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
