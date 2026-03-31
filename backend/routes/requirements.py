"""
routes/requirements.py - NGO Requirement CRUD
"""

from flask import Blueprint, jsonify, request

from access import get_current_user
from db import get_connection

requirements_bp = Blueprint("requirements", __name__)

VALID_REQUIREMENT_STATUSES = ("OPEN", "PARTIALLY_FULFILLED", "FULFILLED")
ACTIVE_DONATION_STATUSES = ("INITIATED", "CONFIRMED", "IN_PROGRESS")


def _require_ngo():
    user = get_current_user()
    if not user:
        return None, (jsonify({"error": "Login required."}), 401)
    if user["role"] != "NGO":
        return None, (jsonify({"error": "NGO access required."}), 403)
    return user, None


def _notify(cur, user_id: int, message: str):
    try:
        cur.execute(
            "INSERT INTO notifications (user_id, message) VALUES (:1, :2)",
            (user_id, message),
        )
    except Exception:
        pass


@requirements_bp.route("/add", methods=["POST"])
def add_requirement():
    user, error = _require_ngo()
    if error:
        return error

    data = request.get_json() or {}
    ngo_id = int(data.get("ngo_id") or 0)
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    quantity = data.get("quantity")

    if ngo_id != user["user_id"]:
        return jsonify({"error": "You can only add requirements for your own NGO account."}), 403
    if not title or quantity in (None, ""):
        return jsonify({"error": "ngo_id, title, and quantity are required."}), 400

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return jsonify({"error": "Quantity must be a valid number."}), 400
    if quantity <= 0:
        return jsonify({"error": "Quantity must be greater than 0."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT ngo_id FROM ngo_profiles WHERE ngo_id = :1", (ngo_id,))
        if not cur.fetchone():
            return jsonify({"error": "NGO not found in system."}), 404

        cur.execute(
            """
            INSERT INTO requirements (ngo_id, title, description, quantity)
            VALUES (:1, :2, :3, :4)
            """,
            (ngo_id, title, description, quantity),
        )
        _notify(cur, ngo_id, f"Your requirement '{title}' (qty: {quantity}) has been posted successfully.")
        conn.commit()
        return jsonify({"message": "Requirement added successfully."}), 201
    except Exception as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        cur.close()
        conn.close()


@requirements_bp.route("/ngo", methods=["GET"])
def get_ngo_requirements():
    user, error = _require_ngo()
    if error:
        return error

    ngo_id = request.args.get("ngo_id", type=int) or user["user_id"]
    if ngo_id != user["user_id"]:
        return jsonify({"error": "You can only view your own requirements."}), 403

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT requirement_id, title, description, quantity, status, created_at
            FROM requirements
            WHERE ngo_id = :1
            ORDER BY created_at DESC
            """,
            (ngo_id,),
        )
        rows = cur.fetchall()
        return jsonify(
            [
                {
                    "requirement_id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "quantity": row[3],
                    "status": row[4],
                    "created_at": str(row[5]),
                }
                for row in rows
            ]
        )
    finally:
        cur.close()
        conn.close()


@requirements_bp.route("/all", methods=["GET"])
def get_all_open():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT r.requirement_id, r.title, r.description, r.quantity,
                   r.status, r.created_at, n.organization_name, n.city
            FROM requirements r
            JOIN ngo_profiles n ON r.ngo_id = n.ngo_id
            WHERE r.status != 'FULFILLED'
            ORDER BY r.created_at DESC
            """
        )
        rows = cur.fetchall()
        return jsonify(
            [
                {
                    "requirement_id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "quantity": row[3],
                    "status": row[4],
                    "created_at": str(row[5]),
                    "ngo_name": row[6],
                    "city": row[7],
                }
                for row in rows
            ]
        )
    finally:
        cur.close()
        conn.close()


@requirements_bp.route("/update", methods=["PUT"])
def update_requirement():
    user, error = _require_ngo()
    if error:
        return error

    data = request.get_json() or {}
    requirement_id = int(data.get("requirement_id") or 0)
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    status = (data.get("status") or "").upper()

    if not requirement_id:
        return jsonify({"error": "requirement_id is required"}), 400
    if not title:
        return jsonify({"error": "Title is required."}), 400
    if status not in VALID_REQUIREMENT_STATUSES:
        return jsonify({"error": f"status must be one of {VALID_REQUIREMENT_STATUSES}"}), 400

    try:
        quantity = int(data.get("quantity"))
    except (TypeError, ValueError):
        return jsonify({"error": "Quantity must be a valid number."}), 400
    if quantity <= 0:
        return jsonify({"error": "Quantity must be greater than 0."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT ngo_id FROM requirements WHERE requirement_id = :1",
            (requirement_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Requirement not found."}), 404
        if row[0] != user["user_id"]:
            return jsonify({"error": "You can only update your own requirements."}), 403

        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM donations
            WHERE requirement_id = :1
              AND donation_status IN ({",".join([f"'{s}'" for s in ACTIVE_DONATION_STATUSES])})
            """,
            (requirement_id,),
        )
        active_count = cur.fetchone()[0]
        if active_count and status in ("OPEN", "FULFILLED"):
            return jsonify(
                {
                    "error": "Requirement status cannot be set to OPEN or FULFILLED while an active donation is in progress."
                }
            ), 400

        cur.execute(
            """
            UPDATE requirements
            SET title = :1,
                description = :2,
                quantity = :3,
                status = :4
            WHERE requirement_id = :5
            """,
            (title, description, quantity, status, requirement_id),
        )
        conn.commit()
        return jsonify({"message": "Requirement updated."})
    except Exception as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        cur.close()
        conn.close()


@requirements_bp.route("/delete", methods=["DELETE"])
def delete_requirement():
    user, error = _require_ngo()
    if error:
        return error

    requirement_id = request.args.get("requirement_id", type=int)
    if not requirement_id:
        return jsonify({"error": "requirement_id is required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT ngo_id FROM requirements WHERE requirement_id = :1",
            (requirement_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Requirement not found."}), 404
        if row[0] != user["user_id"]:
            return jsonify({"error": "You can only delete your own requirements."}), 403

        cur.execute(
            "SELECT COUNT(*) FROM donations WHERE requirement_id = :1",
            (requirement_id,),
        )
        if cur.fetchone()[0]:
            return jsonify(
                {
                    "error": "Requirements with donation history cannot be deleted. Update the status instead."
                }
            ), 400

        cur.execute("DELETE FROM requirements WHERE requirement_id = :1", (requirement_id,))
        conn.commit()
        return jsonify({"message": "Requirement deleted."})
    except Exception as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        cur.close()
        conn.close()


@requirements_bp.route("/<int:requirement_id>", methods=["GET"])
def get_single(requirement_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT r.requirement_id, r.title, r.description, r.quantity,
                   r.status, r.created_at,
                   n.organization_name, n.city, n.address, n.ngo_id
            FROM requirements r
            JOIN ngo_profiles n ON r.ngo_id = n.ngo_id
            WHERE r.requirement_id = :1
            """,
            (requirement_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Requirement not found"}), 404
        return jsonify(
            {
                "requirement_id": row[0],
                "title": row[1],
                "description": row[2],
                "quantity": row[3],
                "status": row[4],
                "created_at": str(row[5]),
                "ngo_name": row[6],
                "city": row[7],
                "address": row[8],
                "ngo_id": row[9],
            }
        )
    finally:
        cur.close()
        conn.close()
