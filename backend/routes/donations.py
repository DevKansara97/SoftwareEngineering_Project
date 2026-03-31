"""
routes/donations.py - Donation lifecycle management
"""

from flask import Blueprint, jsonify, request

from access import get_current_driver, get_current_user
from db import get_connection

donations_bp = Blueprint("donations", __name__)

ACTIVE_STATUSES = ("INITIATED", "CONFIRMED", "IN_PROGRESS")
VALID_STATUSES = ("INITIATED", "CONFIRMED", "IN_PROGRESS", "COMPLETED", "CANCELLED")


def _notify(cur, user_id: int, message: str):
    try:
        cur.execute(
            "INSERT INTO notifications (user_id, message) VALUES (:1, :2)",
            (user_id, message),
        )
    except Exception:
        pass


def _restore_requirement_status(cur, requirement_id: int):
    cur.execute(
        """
        SELECT COUNT(*) FROM donations
        WHERE requirement_id = :1 AND donation_status IN ('COMPLETED')
        """,
        (requirement_id,),
    )
    completed = cur.fetchone()[0]
    if completed:
        cur.execute(
            "UPDATE requirements SET status = 'FULFILLED' WHERE requirement_id = :1",
            (requirement_id,),
        )
        return

    cur.execute(
        """
        SELECT COUNT(*) FROM donations
        WHERE requirement_id = :1 AND donation_status IN ('INITIATED', 'CONFIRMED', 'IN_PROGRESS')
        """,
        (requirement_id,),
    )
    active = cur.fetchone()[0]
    next_status = "PARTIALLY_FULFILLED" if active else "OPEN"
    cur.execute(
        "UPDATE requirements SET status = :1 WHERE requirement_id = :2",
        (next_status, requirement_id),
    )


@donations_bp.route("/create", methods=["POST"])
def create_donation():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Login required."}), 401
    if user["role"] != "DONOR":
        return jsonify({"error": "Only donors can create donations."}), 403

    data = request.get_json() or {}
    requirement_id = int(data.get("requirement_id") or 0)
    donor_id = int(data.get("donor_id") or 0)
    if not requirement_id or donor_id != user["user_id"]:
        return jsonify({"error": "requirement_id and your own donor_id are required."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT status, quantity, ngo_id, title
            FROM requirements
            WHERE requirement_id = :1
            """,
            (requirement_id,),
        )
        req = cur.fetchone()
        if not req:
            return jsonify({"error": "Requirement not found."}), 404
        if req[0] == "FULFILLED" or int(req[1]) <= 0:
            return jsonify({"error": "This requirement is no longer accepting donations."}), 400

        cur.execute(
            "SELECT donor_id FROM donor_profiles WHERE donor_id = :1",
            (donor_id,),
        )
        if not cur.fetchone():
            return jsonify({"error": "Donor profile not found. Please complete your profile."}), 404

        cur.execute(
            """
            SELECT donation_id
            FROM donations
            WHERE requirement_id = :1
              AND donation_status IN ('INITIATED', 'CONFIRMED', 'IN_PROGRESS')
            """,
            (requirement_id,),
        )
        active = cur.fetchone()
        if active:
            return jsonify(
                {
                    "error": "This requirement already has an active donation in progress. Please try another requirement."
                }
            ), 409

        cur.execute(
            """
            INSERT INTO donations (requirement_id, donor_id, donation_status)
            VALUES (:1, :2, 'INITIATED')
            """,
            (requirement_id, donor_id),
        )
        cur.execute(
            """
            SELECT donation_id
            FROM donations
            WHERE requirement_id = :1 AND donor_id = :2
            ORDER BY created_at DESC
            FETCH FIRST 1 ROW ONLY
            """,
            (requirement_id, donor_id),
        )
        donation_id = cur.fetchone()[0]

        cur.execute(
            """
            UPDATE requirements
            SET status = 'PARTIALLY_FULFILLED'
            WHERE requirement_id = :1
            """,
            (requirement_id,),
        )

        _notify(
            cur,
            donor_id,
            f"Your donation for '{req[3]}' has been initiated (Donation ID: {donation_id}).",
        )
        _notify(
            cur,
            req[2],
            f"A donor has initiated a donation for your requirement '{req[3]}'.",
        )

        conn.commit()
        return jsonify({"message": "Donation created successfully.", "donation_id": donation_id}), 201
    except Exception as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        cur.close()
        conn.close()


@donations_bp.route("/status", methods=["PUT"])
def update_status():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Login required."}), 401

    data = request.get_json() or {}
    donation_id = int(data.get("donation_id") or 0)
    new_status = (data.get("status") or "").upper()
    if not donation_id or new_status not in VALID_STATUSES:
        return jsonify({"error": f"status must be one of {VALID_STATUSES}"}), 400

    if new_status in ("IN_PROGRESS", "COMPLETED"):
        return jsonify({"error": "Use the delivery workflow to update in-progress or completed donations."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT d.donation_status, d.donor_id, d.requirement_id, r.ngo_id, r.title
            FROM donations d
            JOIN requirements r ON d.requirement_id = r.requirement_id
            WHERE d.donation_id = :1
            """,
            (donation_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Donation not found."}), 404

        current_status, donor_id, requirement_id, ngo_id, title = row
        allowed = False
        if user["role"] == "DONOR" and donor_id == user["user_id"]:
            allowed = new_status == "CANCELLED" and current_status in ("INITIATED", "CONFIRMED")
        elif user["role"] == "NGO" and ngo_id == user["user_id"]:
            allowed = (
                (new_status == "CONFIRMED" and current_status == "INITIATED")
                or (new_status == "CANCELLED" and current_status in ("INITIATED", "CONFIRMED"))
            )

        if not allowed:
            return jsonify({"error": "You are not allowed to perform that donation status change."}), 403

        cur.execute(
            "UPDATE donations SET donation_status = :1 WHERE donation_id = :2",
            (new_status, donation_id),
        )

        if new_status == "CANCELLED":
            _restore_requirement_status(cur, requirement_id)
            _notify(cur, donor_id, f"Your donation for '{title}' has been cancelled.")
            _notify(cur, ngo_id, f"The donation for your requirement '{title}' has been cancelled.")

        if new_status == "CONFIRMED":
            _notify(cur, donor_id, f"Your donation for '{title}' has been confirmed.")

        conn.commit()
        return jsonify({"message": f"Donation status updated to {new_status}."})
    except Exception as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        cur.close()
        conn.close()


@donations_bp.route("/<int:donation_id>", methods=["GET"])
def get_donation(donation_id):
    user = get_current_user()
    driver = get_current_driver()
    if not user and not driver:
        return jsonify({"error": "Login required."}), 401

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT d.donation_id, d.donation_status, d.created_at,
                   d.donor_id, r.requirement_id, r.title, r.description, r.quantity,
                   r.ngo_id, n.organization_name, n.city,
                   u.name AS donor_name,
                   o.order_id, o.driver_id
            FROM donations d
            JOIN requirements r ON d.requirement_id = r.requirement_id
            JOIN ngo_profiles n ON r.ngo_id = n.ngo_id
            JOIN donor_profiles dp ON d.donor_id = dp.donor_id
            JOIN users u ON dp.donor_id = u.user_id
            LEFT JOIN delivery_orders o ON d.donation_id = o.donation_id
            WHERE d.donation_id = :1
            ORDER BY o.created_at DESC NULLS LAST
            FETCH FIRST 1 ROW ONLY
            """,
            (donation_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Donation not found"}), 404

        if user and user["user_id"] not in (row[3], row[8]):
            return jsonify({"error": "You do not have access to this donation."}), 403
        if driver and row[13] != driver["driver_id"]:
            return jsonify({"error": "You do not have access to this donation."}), 403

        return jsonify(
            {
                "donation_id": row[0],
                "status": row[1],
                "created_at": str(row[2]),
                "donor_id": row[3],
                "requirement_id": row[4],
                "title": row[5],
                "description": row[6],
                "quantity": row[7],
                "ngo_id": row[8],
                "ngo_name": row[9],
                "city": row[10],
                "donor_name": row[11],
                "order_id": row[12],
            }
        )
    finally:
        cur.close()
        conn.close()
