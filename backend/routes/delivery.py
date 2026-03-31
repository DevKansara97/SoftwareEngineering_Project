"""
routes/delivery.py - Delivery order management and driver workflow
"""

import random
import re

from flask import Blueprint, jsonify, request, session

from access import get_current_driver, get_current_user
from db import get_connection

delivery_bp = Blueprint("delivery", __name__)

PROVIDERS = ["Porter", "Rapido", "Uber Connect", "Dunzo", "Shadowfax"]
DELIVERY_STATUSES = ("NOT_DELIVERED", "DELIVERING", "DELIVERED")


def _notify(cur, user_id: int, message: str):
    try:
        cur.execute(
            "INSERT INTO notifications (user_id, message) VALUES (:1, :2)",
            (user_id, message),
        )
    except Exception:
        pass


def _driver_phone_in_use(cur, phone: str, exclude_driver_id=None) -> bool:
    if exclude_driver_id is None:
        cur.execute("SELECT driver_id FROM drivers WHERE phone = :1", (phone,))
    else:
        cur.execute(
            "SELECT driver_id FROM drivers WHERE phone = :1 AND driver_id != :2",
            (phone, int(exclude_driver_id)),
        )
    if cur.fetchone():
        return True

    cur.execute("SELECT user_id FROM users WHERE phone = :1", (phone,))
    return cur.fetchone() is not None


def _driver_has_active_order(cur, driver_id: int, exclude_order_id=None) -> bool:
    sql = """
        SELECT COUNT(*)
        FROM delivery_orders
        WHERE driver_id = :1 AND delivery_status != 'DELIVERED'
    """
    params = [driver_id]
    if exclude_order_id is not None:
        sql += " AND order_id != :2"
        params.append(exclude_order_id)
    cur.execute(sql, params)
    return cur.fetchone()[0] > 0


def _fetch_order_context(cur, order_id: int):
    cur.execute(
        """
        SELECT o.order_id, o.donation_id, o.provider_name, o.driver_id, o.estimated_cost,
               o.tracking_link, o.pickup_time, o.delivery_status, o.created_at,
               d.donor_id, d.donation_status,
               r.requirement_id, r.title, r.description, r.quantity, r.ngo_id,
               n.organization_name, n.city,
               donor_user.name AS donor_name,
               driver.name AS driver_name, driver.phone AS driver_phone, driver.vehicle, driver.status
        FROM delivery_orders o
        JOIN donations d ON o.donation_id = d.donation_id
        JOIN requirements r ON d.requirement_id = r.requirement_id
        JOIN ngo_profiles n ON r.ngo_id = n.ngo_id
        JOIN users donor_user ON d.donor_id = donor_user.user_id
        LEFT JOIN drivers driver ON o.driver_id = driver.driver_id
        WHERE o.order_id = :1
        """,
        (order_id,),
    )
    return cur.fetchone()


def _can_access_order(user, driver, row) -> bool:
    if driver:
        return row[3] == driver["driver_id"]
    if user:
        return user["user_id"] in (row[9], row[15])
    return False


@delivery_bp.route("/estimate", methods=["GET"])
def estimate_cost():
    try:
        distance_km = float(request.args.get("distance_km", 5))
    except ValueError:
        return jsonify({"error": "Invalid distance value"}), 400

    if distance_km <= 0:
        return jsonify({"error": "Distance must be greater than 0."}), 400

    estimates = []
    for provider in PROVIDERS:
        variation = random.uniform(0.85, 1.25)
        cost = round((30 + distance_km * 15) * variation, 2)
        estimates.append(
            {
                "provider": provider,
                "estimated_cost_inr": cost,
                "currency": "INR",
            }
        )
    return jsonify({"estimates": estimates})


@delivery_bp.route("/drivers", methods=["GET"])
def list_drivers():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Login required."}), 401

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT d.driver_id, d.name, d.phone, d.vehicle, d.status,
                   COUNT(CASE WHEN o.delivery_status != 'DELIVERED' THEN 1 END) AS active_orders
            FROM drivers d
            LEFT JOIN delivery_orders o ON d.driver_id = o.driver_id
            GROUP BY d.driver_id, d.name, d.phone, d.vehicle, d.status
            ORDER BY d.name
            """
        )
        rows = cur.fetchall()
        return jsonify(
            [
                {
                    "driver_id": row[0],
                    "name": row[1],
                    "phone": row[2],
                    "vehicle": row[3],
                    "status": row[4],
                    "active_orders": row[5],
                }
                for row in rows
            ]
        )
    finally:
        cur.close()
        conn.close()


@delivery_bp.route("/drivers", methods=["POST"])
def add_driver():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    vehicle = (data.get("vehicle") or "").strip()

    if not name or not phone:
        return jsonify({"error": "Driver name and phone are required."}), 400
    if not re.match(r"^\d{10}$", phone):
        return jsonify({"error": "Driver phone must be exactly 10 digits."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        if _driver_phone_in_use(cur, phone):
            return jsonify({"error": "Driver phone already registered."}), 409

        cur.execute(
            "INSERT INTO drivers (name, phone, vehicle) VALUES (:1, :2, :3)",
            (name, phone, vehicle),
        )
        cur.execute("SELECT driver_id FROM drivers WHERE phone = :1", (phone,))
        driver_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"message": "Driver created.", "driver_id": driver_id}), 201
    except Exception as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        cur.close()
        conn.close()


@delivery_bp.route("/driver-login", methods=["POST"])
def driver_login():
    data = request.get_json() or {}
    phone = (data.get("phone") or "").strip()
    if not re.match(r"^\d{10}$", phone):
        return jsonify({"error": "Enter the registered 10-digit driver phone number."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT driver_id, name, phone, vehicle, status
            FROM drivers
            WHERE phone = :1
            """,
            (phone,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Driver not found. Register first or use the assigned phone number."}), 404

        session.pop("user_id", None)
        session.pop("role", None)
        session.pop("name", None)
        session["driver_id"] = row[0]
        session["driver_name"] = row[1]
        session["driver_phone"] = row[2]

        return jsonify(
            {
                "message": "Driver login successful.",
                "driver_id": row[0],
                "name": row[1],
                "phone": row[2],
                "vehicle": row[3],
                "status": row[4],
                "role": "DRIVER",
            }
        )
    finally:
        cur.close()
        conn.close()


@delivery_bp.route("/driver-logout", methods=["POST"])
def driver_logout():
    for key in ("driver_id", "driver_name", "driver_phone"):
        session.pop(key, None)
    return jsonify({"message": "Driver logged out."})


@delivery_bp.route("/driver/me", methods=["GET"])
def driver_me():
    driver = get_current_driver()
    if not driver:
        return jsonify({"error": "Driver login required."}), 401

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT driver_id, name, phone, vehicle, status, created_at
            FROM drivers
            WHERE driver_id = :1
            """,
            (driver["driver_id"],),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Driver session expired."}), 401
        return jsonify(
            {
                "driver_id": row[0],
                "name": row[1],
                "phone": row[2],
                "vehicle": row[3],
                "status": row[4],
                "created_at": str(row[5]),
            }
        )
    finally:
        cur.close()
        conn.close()


@delivery_bp.route("/driver/orders", methods=["GET"])
def driver_orders():
    driver = get_current_driver()
    if not driver:
        return jsonify({"error": "Driver login required."}), 401

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT o.order_id, o.provider_name, o.estimated_cost, o.pickup_time, o.delivery_status,
                   o.created_at, r.title, r.description, n.organization_name, n.city,
                   donor_user.name, d.donation_status
            FROM delivery_orders o
            JOIN donations d ON o.donation_id = d.donation_id
            JOIN requirements r ON d.requirement_id = r.requirement_id
            JOIN ngo_profiles n ON r.ngo_id = n.ngo_id
            JOIN users donor_user ON d.donor_id = donor_user.user_id
            WHERE o.driver_id = :1
            ORDER BY CASE WHEN o.delivery_status = 'DELIVERED' THEN 1 ELSE 0 END,
                     NVL(o.pickup_time, o.created_at) DESC
            """,
            (driver["driver_id"],),
        )
        rows = cur.fetchall()
        return jsonify(
            [
                {
                    "order_id": row[0],
                    "provider_name": row[1],
                    "estimated_cost": row[2],
                    "pickup_time": str(row[3]) if row[3] else None,
                    "status": row[4],
                    "created_at": str(row[5]),
                    "requirement": row[6],
                    "description": row[7],
                    "ngo_name": row[8],
                    "city": row[9],
                    "donor_name": row[10],
                    "donation_status": row[11],
                }
                for row in rows
            ]
        )
    finally:
        cur.close()
        conn.close()


@delivery_bp.route("/assign", methods=["POST"])
def assign_driver():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Login required."}), 401

    data = request.get_json() or {}
    order_id = int(data.get("order_id") or 0)
    driver_id = int(data.get("driver_id") or 0)
    if not order_id or not driver_id:
        return jsonify({"error": "order_id and driver_id are required."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        row = _fetch_order_context(cur, order_id)
        if not row:
            return jsonify({"error": "Order not found"}), 404
        if user["user_id"] not in (row[9], row[15]):
            return jsonify({"error": "You can only manage orders connected to your own donation or NGO."}), 403
        if row[7] == "DELIVERED":
            return jsonify({"error": "Delivered orders cannot be reassigned."}), 400

        cur.execute(
            "SELECT driver_id, name, phone, vehicle, status FROM drivers WHERE driver_id = :1",
            (driver_id,),
        )
        driver = cur.fetchone()
        if not driver:
            return jsonify({"error": "Driver not found."}), 404

        if _driver_has_active_order(cur, driver_id, exclude_order_id=order_id):
            return jsonify({"error": "That driver already has another active delivery."}), 409

        previous_driver_id = row[3]
        cur.execute(
            "UPDATE delivery_orders SET driver_id = :1 WHERE order_id = :2",
            (driver_id, order_id),
        )
        if previous_driver_id and previous_driver_id != driver_id and not _driver_has_active_order(cur, previous_driver_id):
            cur.execute(
                "UPDATE drivers SET status = 'AVAILABLE' WHERE driver_id = :1",
                (previous_driver_id,),
            )
        cur.execute(
            "UPDATE drivers SET status = 'ON_DELIVERY' WHERE driver_id = :1",
            (driver_id,),
        )

        _notify(
            cur,
            row[9],
            f"Driver {driver[1]} has been assigned to delivery order #{order_id} for '{row[12]}'.",
        )
        _notify(
            cur,
            row[15],
            f"Driver {driver[1]} has been assigned to delivery order #{order_id} for '{row[12]}'.",
        )
        conn.commit()
        return jsonify(
            {
                "message": "Driver assigned.",
                "driver": {
                    "driver_id": driver[0],
                    "name": driver[1],
                    "phone": driver[2],
                    "vehicle": driver[3],
                    "status": driver[4],
                },
            }
        )
    except Exception as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        cur.close()
        conn.close()


@delivery_bp.route("/create", methods=["POST"])
def create_order():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Login required."}), 401
    if user["role"] != "DONOR":
        return jsonify({"error": "Only donors can create delivery orders."}), 403

    data = request.get_json() or {}
    donation_id = int(data.get("donation_id") or 0)
    provider_name = (data.get("provider_name") or "").strip()
    estimated_cost = data.get("estimated_cost")
    pickup_time = data.get("pickup_time")

    if not donation_id or not provider_name:
        return jsonify({"error": "donation_id and provider_name are required."}), 400
    if provider_name not in PROVIDERS:
        return jsonify({"error": "Unsupported provider selected."}), 400
    if pickup_time and not re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", pickup_time):
        return jsonify({"error": "pickup_time must be in YYYY-MM-DD HH:MM:SS format."}), 400

    try:
        parsed_cost = float(estimated_cost) if estimated_cost not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify({"error": "estimated_cost must be a valid number."}), 400

    tracking_link = None

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT d.donor_id, d.donation_status, r.title, r.ngo_id
            FROM donations d
            JOIN requirements r ON d.requirement_id = r.requirement_id
            WHERE d.donation_id = :1
            """,
            (donation_id,),
        )
        donation = cur.fetchone()
        if not donation:
            return jsonify({"error": "Donation not found."}), 404
        if donation[0] != user["user_id"]:
            return jsonify({"error": "You can only create delivery orders for your own donations."}), 403
        if donation[1] != "INITIATED":
            return jsonify({"error": "Delivery can only be booked for initiated donations."}), 400

        cur.execute(
            "SELECT order_id FROM delivery_orders WHERE donation_id = :1",
            (donation_id,),
        )
        existing = cur.fetchone()
        if existing:
            return jsonify({"error": "A delivery order already exists for this donation.", "order_id": existing[0]}), 409

        pickup_expr = (
            "TO_TIMESTAMP(:5, 'YYYY-MM-DD HH24:MI:SS')" if pickup_time else "NULL"
        )
        params = [
            donation_id,
            provider_name,
            parsed_cost,
            tracking_link,
        ]
        if pickup_time:
            params.append(pickup_time)

        cur.execute(
            f"""
            INSERT INTO delivery_orders
                (donation_id, provider_name, estimated_cost, tracking_link, pickup_time, delivery_status)
            VALUES (:1, :2, :3, :4, {pickup_expr}, 'NOT_DELIVERED')
            """,
            params,
        )
        cur.execute(
            "SELECT order_id FROM delivery_orders WHERE donation_id = :1",
            (donation_id,),
        )
        order_id = cur.fetchone()[0]
        tracking_link = f"/tracking/{order_id}"
        cur.execute(
            "UPDATE delivery_orders SET tracking_link = :1 WHERE order_id = :2",
            (tracking_link, order_id),
        )

        cur.execute(
            """
            UPDATE donations SET donation_status = 'CONFIRMED'
            WHERE donation_id = :1
            """,
            (donation_id,),
        )

        assigned_driver = None
        cur.execute(
            """
            SELECT d.driver_id, d.name, d.phone, d.vehicle
            FROM drivers d
            WHERE d.status = 'AVAILABLE'
              AND NOT EXISTS (
                  SELECT 1
                  FROM delivery_orders o
                  WHERE o.driver_id = d.driver_id AND o.delivery_status != 'DELIVERED'
              )
            ORDER BY d.created_at
            FETCH FIRST 1 ROW ONLY
            """
        )
        driver = cur.fetchone()
        if driver:
            cur.execute(
                "UPDATE delivery_orders SET driver_id = :1 WHERE order_id = :2",
                (driver[0], order_id),
            )
            cur.execute(
                "UPDATE drivers SET status = 'ON_DELIVERY' WHERE driver_id = :1",
                (driver[0],),
            )
            assigned_driver = {
                "driver_id": driver[0],
                "name": driver[1],
                "phone": driver[2],
                "vehicle": driver[3],
            }

        _notify(
            cur,
            donation[0],
            f"Delivery order #{order_id} confirmed via {provider_name} for '{donation[2]}'.",
        )
        _notify(
            cur,
            donation[3],
            f"Delivery order #{order_id} has been booked via {provider_name} for '{donation[2]}'.",
        )

        conn.commit()
        return jsonify(
            {
                "message": "Delivery order created.",
                "order_id": order_id,
                "tracking_link": tracking_link,
                "assigned_driver": assigned_driver,
            }
        ), 201
    except Exception as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        cur.close()
        conn.close()


@delivery_bp.route("/<int:order_id>", methods=["GET"])
def get_order(order_id):
    user = get_current_user()
    driver = get_current_driver()
    if not user and not driver:
        return jsonify({"error": "Login required."}), 401

    conn = get_connection()
    cur = conn.cursor()
    try:
        row = _fetch_order_context(cur, order_id)
        if not row:
            return jsonify({"error": "Order not found"}), 404
        if not _can_access_order(user, driver, row):
            return jsonify({"error": "You do not have access to this order."}), 403

        return jsonify(
            {
                "order_id": row[0],
                "donation_id": row[1],
                "provider_name": row[2],
                "estimated_cost": row[4],
                "tracking_link": row[5],
                "pickup_time": str(row[6]) if row[6] else None,
                "status": row[7],
                "created_at": str(row[8]),
                "donor_id": row[9],
                "donation_status": row[10],
                "requirement_id": row[11],
                "requirement": row[12],
                "description": row[13],
                "quantity": row[14],
                "ngo_id": row[15],
                "ngo_name": row[16],
                "city": row[17],
                "donor_name": row[18],
                "driver": {
                    "driver_id": row[3],
                    "name": row[19],
                    "phone": row[20],
                    "vehicle": row[21],
                    "status": row[22],
                }
                if row[3]
                else None,
            }
        )
    finally:
        cur.close()
        conn.close()


@delivery_bp.route("/status", methods=["PUT"])
def update_status():
    driver = get_current_driver()
    if not driver:
        return jsonify({"error": "Only logged-in drivers can update delivery status."}), 401

    data = request.get_json() or {}
    order_id = int(data.get("order_id") or 0)
    status = (data.get("status") or "").upper()
    if not order_id or status not in DELIVERY_STATUSES:
        return jsonify({"error": f"status must be one of {DELIVERY_STATUSES}"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        row = _fetch_order_context(cur, order_id)
        if not row:
            return jsonify({"error": "Order not found."}), 404
        if row[3] != driver["driver_id"]:
            return jsonify({"error": "Only the assigned driver can update this order."}), 403

        current_status = row[7]
        valid_transitions = {
            "NOT_DELIVERED": {"DELIVERING"},
            "DELIVERING": {"DELIVERED"},
            "DELIVERED": set(),
        }
        if status == current_status:
            return jsonify({"message": f"Delivery status is already {status}."})
        if status not in valid_transitions[current_status]:
            return jsonify({"error": f"Cannot change delivery status from {current_status} to {status}."}), 400

        cur.execute(
            "UPDATE delivery_orders SET delivery_status = :1 WHERE order_id = :2",
            (status, order_id),
        )

        if status == "DELIVERING":
            cur.execute(
                "UPDATE donations SET donation_status = 'IN_PROGRESS' WHERE donation_id = :1",
                (row[1],),
            )
            cur.execute(
                "UPDATE drivers SET status = 'ON_DELIVERY' WHERE driver_id = :1",
                (driver["driver_id"],),
            )

        if status == "DELIVERED":
            cur.execute(
                "UPDATE donations SET donation_status = 'COMPLETED' WHERE donation_id = :1",
                (row[1],),
            )
            cur.execute(
                "UPDATE requirements SET status = 'FULFILLED' WHERE requirement_id = :1",
                (row[11],),
            )
            cur.execute(
                "UPDATE drivers SET status = 'AVAILABLE' WHERE driver_id = :1",
                (driver["driver_id"],),
            )
            _notify(cur, row[9], f"Delivery order #{order_id} for '{row[12]}' has been completed.")
            _notify(cur, row[15], f"Delivery order #{order_id} for '{row[12]}' has been completed.")

        conn.commit()
        return jsonify({"message": f"Delivery status updated to {status}."})
    except Exception as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        cur.close()
        conn.close()


@delivery_bp.route("/donation/<int:donation_id>", methods=["GET"])
def get_by_donation(donation_id):
    user = get_current_user()
    driver = get_current_driver()
    if not user and not driver:
        return jsonify({"error": "Login required."}), 401

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT o.order_id
            FROM delivery_orders o
            WHERE o.donation_id = :1
            ORDER BY o.created_at DESC
            FETCH FIRST 1 ROW ONLY
            """,
            (donation_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({}), 200

        order = _fetch_order_context(cur, row[0])
        if not order:
            return jsonify({}), 200
        if not _can_access_order(user, driver, order):
            return jsonify({"error": "You do not have access to this order."}), 403

        return jsonify(
            {
                "order_id": order[0],
                "donation_id": order[1],
                "provider_name": order[2],
                "estimated_cost": order[4],
                "tracking_link": order[5],
                "pickup_time": str(order[6]) if order[6] else None,
                "status": order[7],
                "created_at": str(order[8]),
                "requirement": order[12],
                "ngo_name": order[16],
                "city": order[17],
                "driver": {
                    "driver_id": order[3],
                    "name": order[19],
                    "phone": order[20],
                    "vehicle": order[21],
                    "status": order[22],
                }
                if order[3]
                else None,
            }
        )
    finally:
        cur.close()
        conn.close()
