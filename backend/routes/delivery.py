"""
routes/delivery.py  –  Delivery order management + mock cost estimation
Maps to: FR-9, FR-12 to FR-15, 3rd-Party Service Integration Module
"""

import random
from flask import Blueprint, request, jsonify
from db import get_connection

delivery_bp = Blueprint('delivery', __name__)

# Mock service providers (replace with real API calls)
PROVIDERS = ['Porter', 'Rapido', 'Uber Connect', 'Dunzo', 'Shadowfax']


# ── GET /api/delivery/estimate?distance_km=X ─────────────────────────────────
# Mock cost estimation – replace with real API call to Porter / Rapido etc.

@delivery_bp.route('/estimate', methods=['GET'])
def estimate_cost():
    try:
        distance_km = float(request.args.get('distance_km', 5))
    except ValueError:
        return jsonify({'error': 'Invalid distance value'}), 400

    base_rate     = 15   # INR per km
    base_charge   = 30   # INR fixed
    estimates = []
    for provider in PROVIDERS:
        variation = random.uniform(0.85, 1.25)
        cost      = round((base_charge + distance_km * base_rate) * variation, 2)
        estimates.append({
            'provider': provider,
            'estimated_cost_inr': cost,
            'currency': 'INR'
        })
    return jsonify({'estimates': estimates})


# ── POST /api/delivery/create ─────────────────────────────────────────────────

@delivery_bp.route('/create', methods=['POST'])
def create_order():
    data          = request.get_json()
    donation_id   = data.get('donation_id')
    provider_name = data.get('provider_name')
    estimated_cost= data.get('estimated_cost')
    pickup_time   = data.get('pickup_time')   # ISO string or None

    if not all([donation_id, provider_name]):
        return jsonify({'error': 'donation_id and provider_name are required.'}), 400

    # Mock tracking link
    tracking_link = f"https://track.sevaconnect.in/order/{donation_id}"

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO delivery_orders
                (donation_id, provider_name, estimated_cost, tracking_link,
                 pickup_time, delivery_status)
            VALUES (:1, :2, :3, :4,
                    TO_TIMESTAMP(:5, 'YYYY-MM-DD HH24:MI:SS'),
                    'NOT_DELIVERED')
        """, (
            int(donation_id), provider_name,
            float(estimated_cost) if estimated_cost else None,
            tracking_link,
            pickup_time or None
        ))
        conn.commit()

        # Update donation to CONFIRMED
        cur.execute("""
            UPDATE donations SET donation_status = 'CONFIRMED'
            WHERE donation_id = :1
        """, (int(donation_id),))
        conn.commit()

        # Get donor and NGO to notify
        cur.execute("""
            SELECT d.donor_id, r.ngo_id, r.title
            FROM donations d
            JOIN requirements r ON d.requirement_id = r.requirement_id
            WHERE d.donation_id = :1
        """, (int(donation_id),))
        row = cur.fetchone()
        if row:
            donor_id, ngo_id, title = row
            _notify(cur, conn, donor_id,
                    f"Delivery confirmed via {provider_name} for '{title}'. "
                    f"Tracking: {tracking_link}")
            _notify(cur, conn, ngo_id,
                    f"Delivery for your requirement '{title}' is confirmed via {provider_name}. "
                    f"Estimated cost: ₹{estimated_cost}.")

        return jsonify({
            'message':       'Delivery order created.',
            'tracking_link': tracking_link
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ── GET /api/delivery/<order_id> ──────────────────────────────────────────────

@delivery_bp.route('/<int:order_id>', methods=['GET'])
def get_order(order_id):
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT o.order_id, o.provider_name, o.estimated_cost,
                   o.tracking_link, o.pickup_time, o.delivery_status, o.created_at,
                   r.title
            FROM delivery_orders o
            JOIN donations d ON o.donation_id = d.donation_id
            JOIN requirements r ON d.requirement_id = r.requirement_id
            WHERE o.order_id = :1
        """, (order_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Order not found'}), 404
        return jsonify({
            'order_id':       row[0],
            'provider_name':  row[1],
            'estimated_cost': row[2],
            'tracking_link':  row[3],
            'pickup_time':    str(row[4]) if row[4] else None,
            'status':         row[5],
            'created_at':     str(row[6]),
            'requirement':    row[7]
        })
    finally:
        cur.close()
        conn.close()


# ── PUT /api/delivery/status ──────────────────────────────────────────────────

@delivery_bp.route('/status', methods=['PUT'])
def update_status():
    data     = request.get_json()
    order_id = data.get('order_id')
    status   = (data.get('status') or '').upper()

    valid = ('NOT_DELIVERED', 'DELIVERING', 'DELIVERED')
    if status not in valid:
        return jsonify({'error': f'status must be one of {valid}'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE delivery_orders SET delivery_status = :1 WHERE order_id = :2
        """, (status, int(order_id)))
        conn.commit()

        if status == 'DELIVERED':
            # Mark donation COMPLETED
            cur.execute("""
                UPDATE donations SET donation_status = 'COMPLETED'
                WHERE donation_id = (
                    SELECT donation_id FROM delivery_orders WHERE order_id = :1
                )
            """, (int(order_id),))
            conn.commit()

        return jsonify({'message': f'Delivery status updated to {status}.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ── GET /api/delivery/donation/<donation_id> ──────────────────────────────────

@delivery_bp.route('/donation/<int:donation_id>', methods=['GET'])
def get_by_donation(donation_id):
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT order_id, provider_name, estimated_cost,
                   tracking_link, pickup_time, delivery_status, created_at
            FROM delivery_orders
            WHERE donation_id = :1
            ORDER BY created_at DESC
            FETCH FIRST 1 ROW ONLY
        """, (donation_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({}), 200
        return jsonify({
            'order_id':       row[0],
            'provider_name':  row[1],
            'estimated_cost': row[2],
            'tracking_link':  row[3],
            'pickup_time':    str(row[4]) if row[4] else None,
            'status':         row[5],
            'created_at':     str(row[6])
        })
    finally:
        cur.close()
        conn.close()


def _notify(cur, conn, user_id: int, message: str):
    try:
        cur.execute("INSERT INTO notifications (user_id, message) VALUES (:1, :2)",
                    (user_id, message))
        conn.commit()
    except Exception:
        pass
