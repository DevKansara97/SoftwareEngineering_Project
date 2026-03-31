"""
routes/ngo.py - NGO profile management
"""

import re

from flask import Blueprint, jsonify, request

from access import get_current_user
from db import get_connection

ngo_bp = Blueprint("ngo", __name__)


def _require_ngo():
    user = get_current_user()
    if not user:
        return None, (jsonify({"error": "Login required."}), 401)
    if user["role"] != "NGO":
        return None, (jsonify({"error": "NGO access required."}), 403)
    return user, None


@ngo_bp.route("/profile", methods=["GET"])
def get_profile():
    user, error = _require_ngo()
    if error:
        return error

    ngo_id = request.args.get("ngo_id", type=int) or user["user_id"]
    if ngo_id != user["user_id"]:
        return jsonify({"error": "You can only view your own NGO profile."}), 403

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT u.user_id, u.name, u.email, u.phone,
                   n.organization_name, n.address, n.city, n.state, n.pincode, n.description
            FROM users u
            JOIN ngo_profiles n ON u.user_id = n.ngo_id
            WHERE u.user_id = :1
            """,
            (ngo_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "NGO not found"}), 404
        return jsonify(
            {
                "user_id": row[0],
                "name": row[1],
                "email": row[2],
                "phone": row[3],
                "organization_name": row[4],
                "address": row[5],
                "city": row[6],
                "state": row[7],
                "pincode": row[8],
                "description": row[9],
            }
        )
    finally:
        cur.close()
        conn.close()


@ngo_bp.route("/profile", methods=["PUT"])
def update_profile():
    user, error = _require_ngo()
    if error:
        return error

    data = request.get_json() or {}
    ngo_id = int(data.get("ngo_id") or 0)
    if ngo_id != user["user_id"]:
        return jsonify({"error": "You can only update your own NGO profile."}), 403

    phone = (data.get("phone") or "").strip()
    pincode = (data.get("pincode") or "").strip()

    if phone and not re.match(r"^\d{10}$", phone):
        return jsonify({"error": "Phone must be exactly 10 digits."}), 400
    if pincode and not re.match(r"^\d{6}$", pincode):
        return jsonify({"error": "Pincode must be exactly 6 digits."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT user_id FROM users
            WHERE phone = :1 AND user_id != :2
            """,
            (phone, ngo_id),
        )
        if phone and cur.fetchone():
            return jsonify({"error": "Phone already in use by another account."}), 409

        cur.execute("SELECT driver_id FROM drivers WHERE phone = :1", (phone,))
        if phone and cur.fetchone():
            return jsonify({"error": "Phone already in use by a driver."}), 409

        cur.execute(
            """
            UPDATE ngo_profiles
            SET organization_name = :1,
                address           = :2,
                city              = :3,
                state             = :4,
                pincode           = :5,
                description       = :6
            WHERE ngo_id = :7
            """,
            (
                (data.get("organization_name") or "").strip(),
                (data.get("address") or "").strip(),
                (data.get("city") or "").strip(),
                (data.get("state") or "").strip(),
                pincode,
                (data.get("description") or "").strip(),
                ngo_id,
            ),
        )
        cur.execute(
            "UPDATE users SET name = :1, phone = :2 WHERE user_id = :3",
            ((data.get("name") or "").strip(), phone or None, ngo_id),
        )
        conn.commit()
        return jsonify({"message": "Profile updated successfully."})
    except Exception as exc:
        conn.rollback()
        if "ORA-00001" in str(exc):
            return jsonify({"error": "Phone already in use."}), 409
        return jsonify({"error": str(exc)}), 500
    finally:
        cur.close()
        conn.close()


@ngo_bp.route("/all", methods=["GET"])
def list_all():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT u.user_id, u.name, n.organization_name, n.city, n.state, n.description
            FROM users u
            JOIN ngo_profiles n ON u.user_id = n.ngo_id
            ORDER BY n.organization_name
            """
        )
        rows = cur.fetchall()
        return jsonify(
            [
                {
                    "ngo_id": row[0],
                    "name": row[1],
                    "organization_name": row[2],
                    "city": row[3],
                    "state": row[4],
                    "description": row[5],
                }
                for row in rows
            ]
        )
    finally:
        cur.close()
        conn.close()
