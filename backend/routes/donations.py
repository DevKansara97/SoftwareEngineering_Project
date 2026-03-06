"""
routes/donations.py  –  Donation lifecycle management
Maps to: DonationManagementModule, FR-7 to FR-11
"""

from flask import Blueprint, request, jsonify
from db import get_connection

donations_bp = Blueprint('donations', __name__)


# ── POST /api/donations/create ────────────────────────────────────────────────

@donations_bp.route('/create', methods=['POST'])
def create_donation():
    data           = request.get_json()
    requirement_id = data.get('requirement_id')
    donor_id       = data.get('donor_id')

    if not all([requirement_id, donor_id]):
        return jsonify({'error': 'requirement_id and donor_id are required.'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        # Verify requirement is still open
        cur.execute("""
            SELECT status, quantity, ngo_id, title
            FROM requirements WHERE requirement_id = :1
        """, (int(requirement_id),))
        req = cur.fetchone()
        if not req:
            return jsonify({'error': 'Requirement not found.'}), 404
        if req[0] == 'FULFILLED':
            return jsonify({'error': 'This requirement has already been fulfilled.'}), 400
        if req[1] == 0:
            return jsonify({'error': 'Cannot donate – quantity is 0.'}), 400

        # Verify donor profile exists
        cur.execute("SELECT donor_id FROM donor_profiles WHERE donor_id = :1", (int(donor_id),))
        if not cur.fetchone():
            return jsonify({'error': 'Donor profile not found. Please complete your profile.'}), 404

        # Create donation record
        cur.execute("""
            INSERT INTO donations (requirement_id, donor_id, donation_status)
            VALUES (:1, :2, 'INITIATED')
        """, (int(requirement_id), int(donor_id)))
        conn.commit()

        # Get new donation_id
        cur.execute("""
            SELECT donation_id FROM donations
            WHERE requirement_id = :1 AND donor_id = :2
            ORDER BY created_at DESC
            FETCH FIRST 1 ROW ONLY
        """, (int(requirement_id), int(donor_id)))
        donation_id = cur.fetchone()[0]

        # Update requirement status
        cur.execute("""
            UPDATE requirements SET status = 'PARTIALLY_FULFILLED'
            WHERE requirement_id = :1 AND status = 'OPEN'
        """, (int(requirement_id),))
        conn.commit()

        # Notify donor
        _notify(cur, conn, int(donor_id),
                f"Your donation for '{req[3]}' has been initiated (Donation ID: {donation_id}).")

        # Notify NGO
        _notify(cur, conn, int(req[2]),
                f"A donor has initiated a donation for your requirement '{req[3]}'.")

        return jsonify({
            'message':     'Donation created successfully.',
            'donation_id': donation_id
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ── PUT /api/donations/status ──────────────────────────────────────────────────

@donations_bp.route('/status', methods=['PUT'])
def update_status():
    data        = request.get_json()
    donation_id = data.get('donation_id')
    new_status  = data.get('status', '').upper()

    valid = ('INITIATED', 'CONFIRMED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')
    if new_status not in valid:
        return jsonify({'error': f'status must be one of {valid}'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE donations SET donation_status = :1 WHERE donation_id = :2
        """, (new_status, int(donation_id)))
        conn.commit()

        # If completed → mark requirement FULFILLED
        if new_status == 'COMPLETED':
            cur.execute("""
                UPDATE requirements r
                SET status = 'FULFILLED'
                WHERE r.requirement_id = (
                    SELECT requirement_id FROM donations WHERE donation_id = :1
                )
            """, (int(donation_id),))
            conn.commit()

        return jsonify({'message': f'Donation status updated to {new_status}.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ── GET /api/donations/<id> ───────────────────────────────────────────────────

@donations_bp.route('/<int:donation_id>', methods=['GET'])
def get_donation(donation_id):
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT d.donation_id, d.donation_status, d.created_at,
                   r.title, r.description, r.quantity,
                   n.organization_name, n.city,
                   u.name AS donor_name
            FROM donations d
            JOIN requirements   r ON d.requirement_id = r.requirement_id
            JOIN ngo_profiles   n ON r.ngo_id = n.ngo_id
            JOIN donor_profiles dp ON d.donor_id = dp.donor_id
            JOIN users          u  ON dp.donor_id = u.user_id
            WHERE d.donation_id = :1
        """, (donation_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Donation not found'}), 404
        return jsonify({
            'donation_id': row[0], 'status': row[1], 'created_at': str(row[2]),
            'title': row[3], 'description': row[4], 'quantity': row[5],
            'ngo_name': row[6], 'city': row[7], 'donor_name': row[8]
        })
    finally:
        cur.close()
        conn.close()


# ── internal helper ───────────────────────────────────────────────────────────

def _notify(cur, conn, user_id: int, message: str):
    try:
        cur.execute("""
            INSERT INTO notifications (user_id, message) VALUES (:1, :2)
        """, (user_id, message))
        conn.commit()
    except Exception:
        pass
