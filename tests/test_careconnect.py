import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app          # noqa: E402
from gestures import classify_gesture, classify_reading  # noqa: E402


class GestureTests(unittest.TestCase):
    def test_each_quadrant(self):
        self.assertEqual(classify_gesture(-5000, 5000).code, "UL")
        self.assertEqual(classify_gesture(5000, 5000).code, "UR")
        self.assertEqual(classify_gesture(-5000, -5000).code, "LL")
        self.assertEqual(classify_gesture(5000, -5000).code, "LR")

    def test_help_and_rest(self):
        self.assertEqual(classify_gesture(0, -2000).code, "U")
        self.assertIsNone(classify_gesture(100, 200))

    def test_threshold_is_configurable(self):
        self.assertIsNone(classify_gesture(3500, 3500))
        self.assertEqual(classify_gesture(3500, 3500, threshold=3000).code, "UR")

    def test_high_temperature_outranks_gesture(self):
        self.assertEqual(classify_reading(5000, 5000, 38.5).code, "TH")
        self.assertEqual(classify_reading(5000, 5000, 36.5).code, "UR")


class ApiTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.client = create_app(self.path).test_client()
        r = self.client.post("/api/patients", json={"name": "Asha", "bed_number": 7})
        self.pid = r.get_json()["id"]

    def tearDown(self):
        os.remove(self.path)

    def reading(self, **kw):
        return self.client.post("/api/readings", json={"patient_id": self.pid, **kw})

    def test_duplicate_bed_rejected(self):
        r = self.client.post("/api/patients", json={"name": "Ravi", "bed_number": 7})
        self.assertEqual(r.status_code, 409)

    def test_invalid_patient_payload(self):
        r = self.client.post("/api/patients", json={"name": "", "bed_number": "x"})
        self.assertEqual(r.status_code, 400)

    def test_normal_reading_creates_no_alert(self):
        r = self.reading(accel_x=0, accel_y=0, temperature=36.6)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/alerts").get_json(), [])

    def test_unknown_patient(self):
        r = self.client.post("/api/readings", json={"patient_id": 999, "accel_x": 0, "accel_y": 0})
        self.assertEqual(r.status_code, 404)

    def test_alerts_sorted_by_priority(self):
        self.reading(accel_x=-5000, accel_y=5000)      # routine (food)
        self.reading(accel_x=5000, accel_y=5000)       # attention (nurse)
        self.reading(accel_x=0, accel_y=-2000)         # emergency (help)
        priorities = [a["priority"] for a in self.client.get("/api/alerts").get_json()]
        self.assertEqual(priorities, ["emergency", "attention", "routine"])

    def test_acknowledge_flow_and_stats(self):
        alert_id = self.reading(accel_x=0, accel_y=-2000).get_json()["alert_id"]
        self.assertEqual(self.client.get("/api/stats").get_json()["open_alerts"], 1)

        ack = self.client.post(f"/api/alerts/{alert_id}/ack")
        self.assertEqual(ack.status_code, 200)
        self.assertEqual(self.client.post(f"/api/alerts/{alert_id}/ack").status_code, 409)
        self.assertEqual(self.client.post("/api/alerts/12345/ack").status_code, 404)

        stats = self.client.get("/api/stats").get_json()
        self.assertEqual(stats["open_alerts"], 0)
        self.assertIsNotNone(stats["avg_response_seconds"])
        self.assertEqual(stats["by_priority"]["emergency"], 1)

    def test_bad_status_filter(self):
        self.assertEqual(self.client.get("/api/alerts?status=bogus").status_code, 400)


if __name__ == "__main__":
    unittest.main()
