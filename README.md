# CareConnect – Python Alert Server

Python backend for **CareConnect**, my B.Tech project (KIIT, School of Electronics Engineering): an IoT-based
medical message conveyer system that lets bedridden patients call for help using hand gestures.

The original project used an ESP32 + MPU6050 wearable, LoRa/Blynk and a Kotlin Android app. This repository
re-implements the **server-side logic in Python** so it can be run, tested and demonstrated on any PC without hardware.

## What it does
- Classifies raw accelerometer (MPU6050) readings into gestures, ported from the ESP32 firmware logic
  (upper-left = need food, upper-right = call nurse, lower-left = need medicine, lower-right = washroom,
  tilt = need help)
- Raises an **emergency** alert when body temperature is 38.0 °C or above (overrides any gesture)
- Stores patients and alerts in **SQLite**
- Returns open alerts **sorted by priority** (emergency, attention, routine), oldest first
- Lets caregivers **acknowledge** alerts and tracks the average response time
- Includes a **sensor simulator** and **unit/API tests**

## Tech stack
Python 3.10+, Flask, SQLite (`sqlite3`), `unittest`

## Project structure
```
app.py          Flask REST API
gestures.py     Gesture and temperature classification
db.py           SQLite schema and helpers
simulator.py    Fake wearable that posts random readings
tests/          11 unit and API tests
requirements.txt
```

## Setup and run
```bash
pip install -r requirements.txt
python app.py              # server on http://127.0.0.1:5000
python simulator.py        # in a second terminal
python -m unittest discover -s tests -v
```

## API
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/patients` | Add patient `{name, bed_number}` |
| GET | `/api/patients` | List patients |
| POST | `/api/readings` | Send `{patient_id, accel_x, accel_y, temperature}`; creates an alert if needed |
| GET | `/api/alerts?status=open` | Alerts, most urgent first (`open` / `acknowledged`) |
| POST | `/api/alerts/<id>/ack` | Acknowledge an alert |
| GET | `/api/stats` | Totals, per-priority counts, average response time |

Example:
```bash
curl -X POST localhost:5000/api/patients -H "Content-Type: application/json" -d '{"name":"Asha","bed_number":7}'
curl -X POST localhost:5000/api/readings -H "Content-Type: application/json" -d '{"patient_id":1,"accel_x":0,"accel_y":-2000,"temperature":36.8}'
curl localhost:5000/api/alerts
```

## My role
Hardware and Android work on the original team project (with Souravjit Bal and Arka Banerjee), and the Python port of the alert logic and API in this repository.

## Possible improvements
Authentication, WebSocket push for live alerts, MQTT ingestion from the real ESP32, a web dashboard.
