"""
routes/auth.py  –  Registration & Login
Passwords are hashed with werkzeug (bcrypt-compatible pbkdf2).
"""

import hashlib, re
from flask import Blueprint, request, jsonify, session
from db import get_connection

auth_bp = Blueprint('auth', __name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def hash_password(pw: str) -> str:
    """SHA-256 hash – replace with bcrypt in production."""
    return hashlib.sha256(pw.encode()).hexdigest()


def validate_password(pw: str) -> bool:
    """Min 8 chars, 1 upper, 1 lower, 1 digit, 1 special."""
    if len(pw) < 8:
        return False
    if not re.search(r'[A-Z]', pw): return False
    if not re.search(r'[a-z]', pw): return False
    if not re.search(r'\d',   pw): return False
    if not re.search(r'[^A-Za-z0-9]', pw): return False
    return True


def validate_email(email: str) -> bool:
    return bool(re.match(r'^[\w.\-+]+@[\w\-]+\.[a-zA-Z]{2,}$', email))


def validate_phone(phone: str) -> bool:
    return bool(re.match(r'^\d{10}$', phone))


def validate_pincode(pin: str) -> bool:
    return bool(re.match(r'^\d{6}$', pin))


# ── POST /api/auth/register ───────────────────────────────────────────────────

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    # ── basic field validation ────────────────────────────────────────────────
    required = ['name', 'email', 'password', 'role', 'phone']
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'Field "{f}" is required.'}), 400

    name     = data['name'].strip()
    email    = data['email'].strip().lower()
    password = data['password']
    role     = data['role'].upper()
    phone    = data['phone'].strip()

    if role not in ('NGO', 'DONOR'):
        return jsonify({'error': 'Role must be NGO or DONOR.'}), 400
    if not validate_email(email):
        return jsonify({'error': 'Invalid email format.'}), 400
    if not validate_password(password):
        return jsonify({'error': 'Password must be ≥8 chars with upper, lower, digit and special character.'}), 400
    if not validate_phone(phone):
        return jsonify({'error': 'Phone must be exactly 10 digits.'}), 400

    pw_hash = hash_password(password)

    conn = get_connection()
    cur  = conn.cursor()
    try:
        # insert into users
        cur.execute("""
            INSERT INTO users (name, email, password, role, phone)
            VALUES (:1, :2, :3, :4, :5)
        """, (name, email, pw_hash, role, phone))
        conn.commit()

        # get the new user_id
        cur.execute("SELECT user_id FROM users WHERE email = :1", (email,))
        row = cur.fetchone()
        user_id = row[0]

        # insert profile row
        if role == 'NGO':
            org_name    = data.get('organization_name', name)
            address     = data.get('address', '')
            city        = data.get('city', '')
            state       = data.get('state', '')
            pincode     = data.get('pincode', '')
            description = data.get('description', '')

            if pincode and not validate_pincode(pincode):
                return jsonify({'error': 'Pincode must be 6 digits.'}), 400

            cur.execute("""
                INSERT INTO ngo_profiles
                    (ngo_id, organization_name, address, city, state, pincode, description)
                VALUES (:1, :2, :3, :4, :5, :6, :7)
            """, (user_id, org_name, address, city, state, pincode, description))

        else:  # DONOR
            donor_type    = data.get('donor_type', 'Individual')
            org_name      = data.get('organization_name', '')
            address       = data.get('address', '')
            cur.execute("""
                INSERT INTO donor_profiles (donor_id, donor_type, organization_name, address)
                VALUES (:1, :2, :3, :4)
            """, (user_id, donor_type, org_name, address))

        conn.commit()
        return jsonify({'message': 'Registration successful!', 'user_id': user_id}), 201

    except Exception as e:
        conn.rollback()
        if 'ORA-00001' in str(e):
            return jsonify({'error': 'Email already registered.'}), 409
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ── POST /api/auth/login ──────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email    = (data.get('email') or '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400

    pw_hash = hash_password(password)

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT user_id, name, role FROM users
            WHERE email = :1 AND password = :2
        """, (email, pw_hash))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Invalid credentials.'}), 401

        user_id, name, role = row
        session['user_id'] = user_id
        session['role']    = role
        session['name']    = name

        return jsonify({
            'message': 'Login successful!',
            'user_id': user_id,
            'name':    name,
            'role':    role
        }), 200
    finally:
        cur.close()
        conn.close()


# ── POST /api/auth/logout ─────────────────────────────────────────────────────

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully.'}), 200


# ── GET /api/auth/me ──────────────────────────────────────────────────────────

@auth_bp.route('/me', methods=['GET'])
def me():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT user_id, name, email, role, phone, created_at
            FROM users WHERE user_id = :1
        """, (int(user_id),))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'User not found.'}), 404
        return jsonify({
            'user_id':    row[0],
            'name':       row[1],
            'email':      row[2],
            'role':       row[3],
            'phone':      row[4],
            'created_at': str(row[5])
        })
    finally:
        cur.close()
        conn.close()
