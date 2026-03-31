"""
routes/donor.py - Donor profile management
"""

import re

from flask import Blueprint, jsonify, request

from access import get_current_user
from db import get_connection

donor_bp = Blueprint("donor", __name__)


def _require_donor():
    user = get_current_user()
    if not user:
        return None, (jsonify({"error": "Login required."}), 401)
    if user["role"] != "DONOR":
        return None, (jsonify({"error": "Donor access required."}), 403)
    return user, None


@donor_bp.route("/profile", methods=["GET"])
def get_profile():
    user, error = _require_donor()
    if error:
        return error

    donor_id = request.args.get("donor_id", type=int) or user["user_id"]
    if donor_id != user["user_id"]:
        return jsonify({"error": "You can only view your own donor profile."}), 403

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT u.user_id, u.name, u.email, u.phone,
                   d.donor_type, d.organization_name, d.address
            FROM users u
            JOIN donor_profiles d ON u.user_id = d.donor_id
            WHERE u.user_id = :1
            """,
            (donor_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Donor not found"}), 404
        return jsonify(
            {
                "user_id": row[0],
                "name": row[1],
                "email": row[2],
                "phone": row[3],
                "donor_type": row[4],
                "organization_name": row[5],
                "address": row[6],
            }
        )
    finally:
        cur.close()
        conn.close()


@donor_bp.route("/profile", methods=["PUT"])
def update_profile():
    user, error = _require_donor()
    if error:
        return error

    data = request.get_json() or {}
    donor_id = int(data.get("donor_id") or 0)
    if donor_id != user["user_id"]:
        return jsonify({"error": "You can only update your own donor profile."}), 403

    phone = (data.get("phone") or "").strip()
    if phone and not re.match(r"^\d{10}$", phone):
        return jsonify({"error": "Phone must be exactly 10 digits."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT user_id FROM users
            WHERE phone = :1 AND user_id != :2
            """,
            (phone, donor_id),
        )
        if phone and cur.fetchone():
            return jsonify({"error": "Phone already in use by another account."}), 409

        cur.execute("SELECT driver_id FROM drivers WHERE phone = :1", (phone,))
        if phone and cur.fetchone():
            return jsonify({"error": "Phone already in use by a driver."}), 409

        cur.execute(
            """
            UPDATE donor_profiles
            SET donor_type = :1,
                organization_name = :2,
                address = :3
            WHERE donor_id = :4
            """,
            (
                (data.get("donor_type") or "Individual").strip(),
                (data.get("organization_name") or "").strip(),
                (data.get("address") or "").strip(),
                donor_id,
            ),
        )
        cur.execute(
            "UPDATE users SET name = :1, phone = :2 WHERE user_id = :3",
            ((data.get("name") or "").strip(), phone or None, donor_id),
        )
        conn.commit()
        return jsonify({"message": "Profile updated."})
    except Exception as exc:
        conn.rollback()
        if "ORA-00001" in str(exc):
            return jsonify({"error": "Phone already in use."}), 409
        return jsonify({"error": str(exc)}), 500
    finally:
        cur.close()
        conn.close()


@donor_bp.route("/donation-history", methods=["GET"])
def donation_history():
    user, error = _require_donor()
    if error:
        return error

    donor_id = request.args.get("donor_id", type=int) or user["user_id"]
    if donor_id != user["user_id"]:
        return jsonify({"error": "You can only view your own donation history."}), 403

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT d.donation_id, r.title, r.description, d.donation_status,
                   d.created_at, n.organization_name, o.order_id
            FROM donations d
            JOIN requirements r ON d.requirement_id = r.requirement_id
            JOIN ngo_profiles n ON r.ngo_id = n.ngo_id
            LEFT JOIN delivery_orders o ON d.donation_id = o.donation_id
            WHERE d.donor_id = :1
            ORDER BY d.created_at DESC
            """,
            (donor_id,),
        )
        rows = cur.fetchall()
        return jsonify(
            [
                {
                    "donation_id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "status": row[3],
                    "created_at": str(row[4]),
                    "ngo_name": row[5],
                    "order_id": row[6],
                }
                for row in rows
            ]
        )
    finally:
        cur.close()
        conn.close()
