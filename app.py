"""CareConnect alert server (Flask + SQLite).

Receives sensor readings from the wearable (or the simulator), turns them
into prioritised alerts, and lets nurses acknowledge them.
"""

import os
import sqlite3
from datetime import datetime

from flask import Flask, jsonify, request

import db
from gestures import PRIORITY_ORDER, classify_reading


def create_app(db_path: str = None) -> Flask:
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or os.environ.get("CARECONNECT_DB", "careconnect.db")
    db.init_db(app.config["DB_PATH"])

    def conn():
        return db.get_connection(app.config["DB_PATH"])

    def error(message, status):
        return jsonify({"error": message}), status

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    # ---------- Patients ----------
    @app.post("/api/patients")
    def add_patient():
        data = request.get_json(silent=True) or {}
        name = str(data.get("name", "")).strip()
        bed = data.get("bed_number")
        if not name or not isinstance(bed, int) or isinstance(bed, bool):
            return error("'name' (text) and 'bed_number' (integer) are required", 400)
        c = conn()
        try:
            cur = c.execute("INSERT INTO patients (name, bed_number) VALUES (?, ?)", (name, bed))
            c.commit()
            return jsonify({"id": cur.lastrowid, "name": name, "bed_number": bed}), 201
        except sqlite3.IntegrityError:
            return error(f"bed {bed} is already assigned", 409)
        finally:
            c.close()

    @app.get("/api/patients")
    def list_patients():
        c = conn()
        try:
            rows = c.execute("SELECT * FROM patients ORDER BY bed_number").fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            c.close()

    # ---------- Sensor readings -> alerts ----------
    @app.post("/api/readings")
    def add_reading():
        data = request.get_json(silent=True) or {}
        try:
            patient_id = int(data["patient_id"])
            ax = int(data.get("accel_x", 0))
            ay = int(data.get("accel_y", 0))
            temp = data.get("temperature")
            temp = float(temp) if temp is not None else None
        except (KeyError, TypeError, ValueError):
            return error("'patient_id' is required; accel_x/accel_y must be integers, "
                         "temperature a number", 400)

        c = conn()
        try:
            if c.execute("SELECT 1 FROM patients WHERE id = ?", (patient_id,)).fetchone() is None:
                return error("patient not found", 404)

            alert = classify_reading(ax, ay, temp)
            if alert is None:
                return jsonify({"alert": None, "status": "normal"}), 200

            cur = c.execute(
                "INSERT INTO alerts (patient_id, code, message, priority, temperature, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (patient_id, alert.code, alert.message, alert.priority, temp, db.now_iso()),
            )
            c.commit()
            return jsonify({"alert_id": cur.lastrowid, "code": alert.code,
                            "message": alert.message, "priority": alert.priority}), 201
        finally:
            c.close()

    # ---------- Alerts ----------
    @app.get("/api/alerts")
    def list_alerts():
        status = request.args.get("status")
        if status not in (None, "open", "acknowledged"):
            return error("status must be 'open' or 'acknowledged'", 400)
        query = ("SELECT a.*, p.name AS patient_name, p.bed_number FROM alerts a "
                 "JOIN patients p ON p.id = a.patient_id")
        params = []
        if status:
            query += " WHERE a.status = ?"
            params.append(status)
        c = conn()
        try:
            rows = [dict(r) for r in c.execute(query, params).fetchall()]
        finally:
            c.close()
        # Most urgent first, then oldest first.
        rows.sort(key=lambda r: (PRIORITY_ORDER[r["priority"]], r["created_at"]))
        return jsonify(rows)

    @app.post("/api/alerts/<int:alert_id>/ack")
    def acknowledge(alert_id):
        c = conn()
        try:
            row = c.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
            if row is None:
                return error("alert not found", 404)
            if row["status"] == "acknowledged":
                return error("alert already acknowledged", 409)
            ts = db.now_iso()
            c.execute("UPDATE alerts SET status='acknowledged', acknowledged_at=? WHERE id=?",
                      (ts, alert_id))
            c.commit()
            return jsonify({"alert_id": alert_id, "status": "acknowledged", "acknowledged_at": ts})
        finally:
            c.close()

    # ---------- Stats ----------
    @app.get("/api/stats")
    def stats():
        c = conn()
        try:
            rows = c.execute("SELECT priority, status, created_at, acknowledged_at FROM alerts").fetchall()
        finally:
            c.close()
        by_priority = {"emergency": 0, "attention": 0, "routine": 0}
        open_count, response_times = 0, []
        for r in rows:
            by_priority[r["priority"]] += 1
            if r["status"] == "open":
                open_count += 1
            elif r["acknowledged_at"]:
                delta = (datetime.fromisoformat(r["acknowledged_at"])
                         - datetime.fromisoformat(r["created_at"]))
                response_times.append(delta.total_seconds())
        avg = round(sum(response_times) / len(response_times), 3) if response_times else None
        return jsonify({"total_alerts": len(rows), "open_alerts": open_count,
                        "by_priority": by_priority, "avg_response_seconds": avg})

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
