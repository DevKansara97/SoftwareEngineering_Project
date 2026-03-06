"""
routes/donor.py  –  Donor profile management
"""

from flask import Blueprint, request, jsonify
from db import get_connection

donor_bp = Blueprint('donor', __name__)


@donor_bp.route('/profile', methods=['GET'])
def get_profile():
    donor_id = request.args.get('donor_id')
    if not donor_id:
        return jsonify({'error': 'donor_id is required'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT u.user_id, u.name, u.email, u.phone,
                   d.donor_type, d.organization_name, d.address
            FROM users u
            JOIN donor_profiles d ON u.user_id = d.donor_id
            WHERE u.user_id = :1
        """, (int(donor_id),))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Donor not found'}), 404
        return jsonify({
            'user_id': row[0], 'name': row[1], 'email': row[2], 'phone': row[3],
            'donor_type': row[4], 'organization_name': row[5], 'address': row[6]
        })
    finally:
        cur.close()
        conn.close()


@donor_bp.route('/profile', methods=['PUT'])
def update_profile():
    data     = request.get_json()
    donor_id = data.get('donor_id')
    if not donor_id:
        return jsonify({'error': 'donor_id is required'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE donor_profiles
            SET donor_type = :1, organization_name = :2, address = :3
            WHERE donor_id = :4
        """, (data.get('donor_type'), data.get('organization_name'), data.get('address'), int(donor_id)))
        cur.execute("""
            UPDATE users SET name = :1, phone = :2 WHERE user_id = :3
        """, (data.get('name'), data.get('phone'), int(donor_id)))
        conn.commit()
        return jsonify({'message': 'Profile updated.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


@donor_bp.route('/donation-history', methods=['GET'])
def donation_history():
    donor_id = request.args.get('donor_id')
    if not donor_id:
        return jsonify({'error': 'donor_id is required'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT d.donation_id, r.title, r.description, d.donation_status,
                   d.created_at, n.organization_name
            FROM donations d
            JOIN requirements r ON d.requirement_id = r.requirement_id
            JOIN ngo_profiles  n ON r.ngo_id = n.ngo_id
            WHERE d.donor_id = :1
            ORDER BY d.created_at DESC
        """, (int(donor_id),))
        rows = cur.fetchall()
        return jsonify([{
            'donation_id': r[0], 'title': r[1], 'description': r[2],
            'status': r[3], 'created_at': str(r[4]), 'ngo_name': r[5]
        } for r in rows])
    finally:
        cur.close()
        conn.close()
