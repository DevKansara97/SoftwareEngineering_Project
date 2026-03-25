"""
routes/auth.py  –  Registration & Login
Passwords are hashed with werkzeug (bcrypt-compatible pbkdf2).
"""

import hashlib, re, os, requests, json
from flask import Blueprint, request, jsonify, session, redirect, url_for
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


# ── Google OAuth Helpers ──────────────────────────────────────────────────────

def get_google_oauth_url(state: str) -> str:
    """Generate Google OAuth authorization URL."""
    client_id = os.getenv('GOOGLE_CLIENT_ID', '')
    if not client_id:
        raise ValueError("GOOGLE_CLIENT_ID not configured in .env")
    
    redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/api/auth/google/callback')
    
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"state={state}&"
        f"access_type=offline"
    )
    return auth_url


def exchange_google_code_for_token(code: str) -> dict:
    """Exchange authorization code for access token."""
    client_id = os.getenv('GOOGLE_CLIENT_ID', '')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '')
    redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/api/auth/google/callback')
    
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }
    
    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        raise ValueError(f"Failed to exchange code: {response.text}")
    
    return response.json()


def get_google_user_info(access_token: str) -> dict:
    """Get user info from Google using access token."""
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {'Authorization': f'Bearer {access_token}'}
    
    response = requests.get(userinfo_url, headers=headers)
    if response.status_code != 200:
        raise ValueError(f"Failed to get user info: {response.text}")
    
    return response.json()


def get_or_create_user_from_google(google_user: dict) -> dict:
    """
    Find or create a user from Google OAuth info.
    Returns user dict with user_id, name, email, role.
    """
    email = google_user.get('email', '').lower().strip()
    name = google_user.get('name', 'Google User')
    
    if not email:
        raise ValueError("Email not provided by Google")
    
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Check if user exists
        cur.execute("SELECT user_id, role FROM users WHERE email = :1", (email,))
        row = cur.fetchone()
        
        if row:
            # User exists
            user_id, role = row
            return {
                'user_id': user_id,
                'name': name,
                'email': email,
                'role': role
            }
        else:
            # User doesn't exist - create new user as DONOR (default for OAuth)
            # Use a placeholder password for OAuth users
            pw_hash = hash_password('oauth_user_no_password')
            
            cur.execute("""
                INSERT INTO users (name, email, password, role, phone)
                VALUES (:1, :2, :3, :4, :5)
            """, (name, email, pw_hash, 'DONOR', '9999999999'))
            
            conn.commit()
            
            # Get the new user_id
            cur.execute("SELECT user_id FROM users WHERE email = :1", (email,))
            row = cur.fetchone()
            user_id = row[0]
            
            # Create donor profile
            cur.execute("""
                INSERT INTO donor_profiles (donor_id, donor_type, organization_name, address)
                VALUES (:1, :2, :3, :4)
            """, (user_id, 'Individual', name, ''))
            
            conn.commit()
            
            return {
                'user_id': user_id,
                'name': name,
                'email': email,
                'role': 'DONOR'
            }
    
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()


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


# ── Google OAuth Flow ─────────────────────────────────────────────────────────

@auth_bp.route('/google/init', methods=['POST'])
def google_auth_init():
    """Initiate Google OAuth flow. Returns authorization URL."""
    try:
        import secrets
        
        # Generate random state to prevent CSRF
        state = secrets.token_urlsafe(32)
        
        # Store state in session (very short-lived)
        session['google_oauth_state'] = state
        session.permanent = True
        
        # Get OAuth URL
        auth_url = get_google_oauth_url(state)
        
        return jsonify({
            'auth_url': auth_url,
            'message': 'Redirect user to this URL for Google login'
        }), 200
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': f'OAuth initialization failed: {str(e)}'}), 500


@auth_bp.route('/google/callback', methods=['GET'])
def google_auth_callback():
    """Callback endpoint after Google OAuth. Returns user data and token."""
    try:
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        if error:
            return jsonify({'error': f'Google OAuth error: {error}'}), 400
        
        if not code or not state:
            return jsonify({'error': 'Missing code or state parameter'}), 400
        
        # Verify state parameter
        stored_state = session.get('google_oauth_state')
        if not stored_state or stored_state != state:
            return jsonify({'error': 'Invalid state parameter - possible CSRF attack'}), 400
        
        # Exchange code for token
        token_data = exchange_google_code_for_token(code)
        access_token = token_data.get('access_token')
        
        if not access_token:
            return jsonify({'error': 'Failed to obtain access token'}), 400
        
        # Get user info from Google
        google_user = get_google_user_info(access_token)
        
        # Get or create user in database
        user = get_or_create_user_from_google(google_user)
        
        # Set session
        session['user_id'] = user['user_id']
        session['role'] = user['role']
        session['name'] = user['name']
        
        # Return user data (frontend will store this in localStorage)
        return jsonify({
            'message': 'Google login successful!',
            'user_id': user['user_id'],
            'name': user['name'],
            'email': user['email'],
            'role': user['role']
        }), 200
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Google callback failed: {str(e)}'}), 500
