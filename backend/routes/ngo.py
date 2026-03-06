"""
routes/ngo.py  –  NGO profile management
"""

from flask import Blueprint, request, jsonify
from db import get_connection

ngo_bp = Blueprint('ngo', __name__)


# ── GET /api/ngo/profile?ngo_id=X ─────────────────────────────────────────────

@ngo_bp.route('/profile', methods=['GET'])
def get_profile():
    ngo_id = request.args.get('ngo_id')
    if not ngo_id:
        return jsonify({'error': 'ngo_id is required'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT u.user_id, u.name, u.email, u.phone,
                   n.organization_name, n.address, n.city, n.state, n.pincode, n.description
            FROM users u
            JOIN ngo_profiles n ON u.user_id = n.ngo_id
            WHERE u.user_id = :1
        """, (int(ngo_id),))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'NGO not found'}), 404
        return jsonify({
            'user_id': row[0], 'name': row[1], 'email': row[2], 'phone': row[3],
            'organization_name': row[4], 'address': row[5], 'city': row[6],
            'state': row[7], 'pincode': row[8], 'description': row[9]
        })
    finally:
        cur.close()
        conn.close()


# ── PUT /api/ngo/profile ───────────────────────────────────────────────────────

@ngo_bp.route('/profile', methods=['PUT'])
def update_profile():
    data   = request.get_json()
    ngo_id = data.get('ngo_id')
    if not ngo_id:
        return jsonify({'error': 'ngo_id is required'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE ngo_profiles
            SET organization_name = :1,
                address           = :2,
                city              = :3,
                state             = :4,
                pincode           = :5,
                description       = :6
            WHERE ngo_id = :7
        """, (
            data.get('organization_name'),
            data.get('address'),
            data.get('city'),
            data.get('state'),
            data.get('pincode'),
            data.get('description'),
            int(ngo_id)
        ))
        # also update name / phone in users
        cur.execute("""
            UPDATE users SET name = :1, phone = :2 WHERE user_id = :3
        """, (data.get('name'), data.get('phone'), int(ngo_id)))
        conn.commit()
        return jsonify({'message': 'Profile updated successfully.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ── GET /api/ngo/all  – list all NGOs for donor search ────────────────────────

@ngo_bp.route('/all', methods=['GET'])
def list_all():
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT u.user_id, u.name, n.organization_name, n.city, n.state, n.description
            FROM users u
            JOIN ngo_profiles n ON u.user_id = n.ngo_id
            ORDER BY n.organization_name
        """)
        rows = cur.fetchall()
        return jsonify([{
            'ngo_id': r[0], 'name': r[1],
            'organization_name': r[2], 'city': r[3],
            'state': r[4], 'description': r[5]
        } for r in rows])
    finally:
        cur.close()
        conn.close()
