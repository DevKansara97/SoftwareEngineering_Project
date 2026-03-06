"""
routes/requirements.py  –  NGO Requirement CRUD
Maps to: RequirementsManagementModule, FR-2, FR-3
"""

from flask import Blueprint, request, jsonify
from db import get_connection

requirements_bp = Blueprint('requirements', __name__)


# ── POST /api/requirements/add ────────────────────────────────────────────────

@requirements_bp.route('/add', methods=['POST'])
def add_requirement():
    data = request.get_json()
    ngo_id      = data.get('ngo_id')
    title       = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    quantity    = data.get('quantity')

    if not all([ngo_id, title, quantity]):
        return jsonify({'error': 'ngo_id, title, and quantity are required.'}), 400
    if int(quantity) <= 0:
        return jsonify({'error': 'Quantity must be greater than 0.'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        # Verify NGO exists
        cur.execute("SELECT ngo_id FROM ngo_profiles WHERE ngo_id = :1", (int(ngo_id),))
        if not cur.fetchone():
            return jsonify({'error': 'NGO not found in system.'}), 404

        cur.execute("""
            INSERT INTO requirements (ngo_id, title, description, quantity)
            VALUES (:1, :2, :3, :4)
        """, (int(ngo_id), title, description, int(quantity)))
        conn.commit()

        # Notify NGO
        _notify(cur, conn, int(ngo_id),
                f"Your requirement '{title}' (qty: {quantity}) has been posted successfully.")

        return jsonify({'message': 'Requirement added successfully.'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ── GET /api/requirements/ngo?ngo_id=X ───────────────────────────────────────

@requirements_bp.route('/ngo', methods=['GET'])
def get_ngo_requirements():
    ngo_id = request.args.get('ngo_id')
    if not ngo_id:
        return jsonify({'error': 'ngo_id is required'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT requirement_id, title, description, quantity, status, created_at
            FROM requirements
            WHERE ngo_id = :1
            ORDER BY created_at DESC
        """, (int(ngo_id),))
        rows = cur.fetchall()
        return jsonify([{
            'requirement_id': r[0], 'title': r[1], 'description': r[2],
            'quantity': r[3], 'status': r[4], 'created_at': str(r[5])
        } for r in rows])
    finally:
        cur.close()
        conn.close()


# ── GET /api/requirements/all  – open requirements (for donors) ───────────────

@requirements_bp.route('/all', methods=['GET'])
def get_all_open():
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT r.requirement_id, r.title, r.description, r.quantity,
                   r.status, r.created_at, n.organization_name, n.city
            FROM requirements r
            JOIN ngo_profiles n ON r.ngo_id = n.ngo_id
            WHERE r.status != 'FULFILLED'
            ORDER BY r.created_at DESC
        """)
        rows = cur.fetchall()
        return jsonify([{
            'requirement_id': r[0], 'title': r[1], 'description': r[2],
            'quantity': r[3], 'status': r[4], 'created_at': str(r[5]),
            'ngo_name': r[6], 'city': r[7]
        } for r in rows])
    finally:
        cur.close()
        conn.close()


# ── PUT /api/requirements/update ──────────────────────────────────────────────

@requirements_bp.route('/update', methods=['PUT'])
def update_requirement():
    data           = request.get_json()
    requirement_id = data.get('requirement_id')
    if not requirement_id:
        return jsonify({'error': 'requirement_id is required'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE requirements
            SET title       = :1,
                description = :2,
                quantity    = :3,
                status      = :4
            WHERE requirement_id = :5
        """, (
            data.get('title'),
            data.get('description'),
            data.get('quantity'),
            data.get('status'),
            int(requirement_id)
        ))
        conn.commit()
        return jsonify({'message': 'Requirement updated.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ── DELETE /api/requirements/delete?requirement_id=X ─────────────────────────

@requirements_bp.route('/delete', methods=['DELETE'])
def delete_requirement():
    requirement_id = request.args.get('requirement_id')
    if not requirement_id:
        return jsonify({'error': 'requirement_id is required'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("DELETE FROM requirements WHERE requirement_id = :1", (int(requirement_id),))
        conn.commit()
        return jsonify({'message': 'Requirement deleted.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ── GET /api/requirements/<id> ────────────────────────────────────────────────

@requirements_bp.route('/<int:requirement_id>', methods=['GET'])
def get_single(requirement_id):
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT r.requirement_id, r.title, r.description, r.quantity,
                   r.status, r.created_at,
                   n.organization_name, n.city, n.address, n.ngo_id
            FROM requirements r
            JOIN ngo_profiles n ON r.ngo_id = n.ngo_id
            WHERE r.requirement_id = :1
        """, (requirement_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Requirement not found'}), 404
        return jsonify({
            'requirement_id': row[0], 'title': row[1], 'description': row[2],
            'quantity': row[3], 'status': row[4], 'created_at': str(row[5]),
            'ngo_name': row[6], 'city': row[7], 'address': row[8], 'ngo_id': row[9]
        })
    finally:
        cur.close()
        conn.close()


# ── internal helper ───────────────────────────────────────────────────────────

def _notify(cur, conn, user_id: int, message: str):
    try:
        cur.execute("""
            INSERT INTO notifications (user_id, message)
            VALUES (:1, :2)
        """, (user_id, message))
        conn.commit()
    except Exception:
        pass
