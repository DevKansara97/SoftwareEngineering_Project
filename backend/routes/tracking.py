"""
routes/tracking.py - Live location tracking for delivery orders
"""

from flask import Blueprint, jsonify, request

from access import get_current_driver, get_current_user
from db import get_connection

tracking_bp = Blueprint("tracking", __name__)


def _fetch_access_context(cur, order_id: int):
    cur.execute(
        """
        SELECT o.order_id, o.driver_id, o.delivery_status, d.donor_id, r.ngo_id
        FROM delivery_orders o
        JOIN donations d ON o.donation_id = d.donation_id
        JOIN requirements r ON d.requirement_id = r.requirement_id
        WHERE o.order_id = :1
        """,
        (order_id,),
    )
    return cur.fetchone()


@tracking_bp.route("/update", methods=["POST"])
def update_location():
    driver = get_current_driver()
    if not driver:
        return jsonify({"error": "Only the assigned driver can push live location updates."}), 401

    data = request.get_json() or {}
    order_id = int(data.get("order_id") or 0)
    lat = data.get("lat")
    lng = data.get("lng")

    if not order_id or lat is None or lng is None:
        return jsonify({"error": "order_id, lat, lng are required"}), 400

    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return jsonify({"error": "lat and lng must be valid coordinates."}), 400

    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return jsonify({"error": "Coordinates are out of range."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        order = _fetch_access_context(cur, order_id)
        if not order:
            return jsonify({"error": "Order not found."}), 404
        if order[1] != driver["driver_id"]:
            return jsonify({"error": "You are not assigned to this order."}), 403
        if order[2] not in ("NOT_DELIVERED", "DELIVERING"):
            return jsonify({"error": "Tracking updates are not allowed for completed deliveries."}), 400

        cur.execute(
            """
            MERGE INTO tracking_locations tl
            USING (SELECT :1 AS order_id FROM dual) src
            ON (tl.order_id = src.order_id)
            WHEN MATCHED THEN
                UPDATE SET lat = :2, lng = :3, updated_at = CURRENT_TIMESTAMP
            WHEN NOT MATCHED THEN
                INSERT (order_id, lat, lng)
                VALUES (:4, :5, :6)
            """,
            (order_id, lat, lng, order_id, lat, lng),
        )
        conn.commit()
        return jsonify({"message": "Location updated."})
    except Exception as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        cur.close()
        conn.close()


@tracking_bp.route("/location", methods=["GET"])
def get_location():
    user = get_current_user()
    driver = get_current_driver()
    if not user and not driver:
        return jsonify({"error": "Login required."}), 401

    order_id = request.args.get("order_id", type=int)
    if not order_id:
        return jsonify({"error": "order_id is required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        order = _fetch_access_context(cur, order_id)
        if not order:
            return jsonify({"error": "Order not found."}), 404

        if driver and order[1] != driver["driver_id"]:
            return jsonify({"error": "You are not assigned to this order."}), 403
        if user and user["user_id"] not in (order[3], order[4]):
            return jsonify({"error": "You do not have access to this order."}), 403

        cur.execute(
            """
            SELECT lat, lng, updated_at
            FROM tracking_locations
            WHERE order_id = :1
            """,
            (order_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"lat": None, "lng": None}), 200
        return jsonify({"lat": row[0], "lng": row[1], "updated_at": str(row[2])})
    finally:
        cur.close()
        conn.close()
