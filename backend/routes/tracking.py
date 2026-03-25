"""
routes/tracking.py  –  Live location tracking for delivery orders
Stores and retrieves lat/lng coordinates pushed by the delivery driver.
For the academic prototype, the frontend simulates driver movement.
"""

from flask import Blueprint, request, jsonify
from db import get_connection

tracking_bp = Blueprint('tracking', __name__)


# ── POST /api/tracking/update  –  push a new location ────────────────────────
# In production: called by the driver's mobile app.
# In prototype:  called by the frontend simulation every few seconds.

@tracking_bp.route('/update', methods=['POST'])
def update_location():
    data     = request.get_json()
    order_id = data.get('order_id')
    lat      = data.get('lat')
    lng      = data.get('lng')

    if not all([order_id, lat, lng]):
        return jsonify({'error': 'order_id, lat, lng are required'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            MERGE INTO tracking_locations tl
            USING (SELECT :1 AS order_id FROM dual) src
            ON (tl.order_id = src.order_id)
            WHEN MATCHED THEN
                UPDATE SET lat = :2, lng = :3, updated_at = CURRENT_TIMESTAMP
            WHEN NOT MATCHED THEN
                INSERT (order_id, lat, lng)
                VALUES (:4, :5, :6)
        """, (int(order_id), float(lat), float(lng),
              int(order_id), float(lat), float(lng)))
        conn.commit()
        return jsonify({'message': 'Location updated.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ── GET /api/tracking/location?order_id=X  –  get latest location ─────────────

@tracking_bp.route('/location', methods=['GET'])
def get_location():
    order_id = request.args.get('order_id')
    if not order_id:
        return jsonify({'error': 'order_id is required'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT lat, lng, updated_at
            FROM tracking_locations
            WHERE order_id = :1
        """, (int(order_id),))
        row = cur.fetchone()
        if not row:
            return jsonify({'lat': None, 'lng': None}), 200
        return jsonify({'lat': row[0], 'lng': row[1], 'updated_at': str(row[2])})
    finally:
        cur.close()
        conn.close()
