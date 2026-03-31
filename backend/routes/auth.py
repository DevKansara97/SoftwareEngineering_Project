"""
routes/auth.py - Registration & Login
Passwords are hashed with SHA-256 for the academic prototype.
"""

import hashlib
import os
import re
import secrets

import requests
from flask import Blueprint, jsonify, request, session

from access import get_current_driver, get_current_user
from db import get_connection

auth_bp = Blueprint("auth", __name__)


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def validate_password(pw: str) -> bool:
    if len(pw) < 8:
        return False
    if not re.search(r"[A-Z]", pw):
        return False
    if not re.search(r"[a-z]", pw):
        return False
    if not re.search(r"\d", pw):
        return False
    if not re.search(r"[^A-Za-z0-9]", pw):
        return False
    return True


def validate_email(email: str) -> bool:
    return bool(
        re.match(
            r"^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+(\.[a-zA-Z0-9\-]+)*\.[a-zA-Z]{2,}$",
            email,
        )
    )


def validate_phone(phone: str) -> bool:
    return bool(re.match(r"^\d{10}$", phone))


def validate_pincode(pin: str) -> bool:
    return bool(re.match(r"^\d{6}$", pin))


def _phone_in_use(cur, phone: str, exclude_user_id=None) -> bool:
    if not phone:
        return False

    if exclude_user_id is None:
        cur.execute("SELECT user_id FROM users WHERE phone = :1", (phone,))
    else:
        cur.execute(
            "SELECT user_id FROM users WHERE phone = :1 AND user_id != :2",
            (phone, int(exclude_user_id)),
        )
    if cur.fetchone():
        return True

    cur.execute("SELECT driver_id FROM drivers WHERE phone = :1", (phone,))
    return cur.fetchone() is not None


def get_google_oauth_url(state: str) -> str:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise ValueError("GOOGLE_CLIENT_ID not configured in .env")

    redirect_uri = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:5000/api/auth/google/callback",
    )
    return (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        "response_type=code&"
        "scope=openid%20email%20profile&"
        f"state={state}&"
        "access_type=offline"
    )


def exchange_google_code_for_token(code: str) -> dict:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    redirect_uri = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:5000/api/auth/google/callback",
    )

    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    if response.status_code != 200:
        raise ValueError(f"Failed to exchange code: {response.text}")
    return response.json()


def get_google_user_info(access_token: str) -> dict:
    response = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20,
    )
    if response.status_code != 200:
        raise ValueError(f"Failed to get user info: {response.text}")
    return response.json()


def get_or_create_user_from_google(google_user: dict) -> dict:
    email = google_user.get("email", "").lower().strip()
    name = google_user.get("name", "Google User").strip() or "Google User"
    if not email:
        raise ValueError("Email not provided by Google")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT user_id, role, name FROM users WHERE email = :1", (email,))
        row = cur.fetchone()
        if row:
            return {
                "user_id": row[0],
                "role": row[1],
                "name": row[2] or name,
                "email": email,
            }

        role_preference = session.get("google_oauth_role", "DONOR")
        role = role_preference if role_preference in ("NGO", "DONOR") else "DONOR"
        pw_hash = hash_password("oauth_user_no_password")

        cur.execute(
            """
            INSERT INTO users (name, email, password, role, phone)
            VALUES (:1, :2, :3, :4, :5)
            """,
            (name, email, pw_hash, role, None),
        )

        cur.execute("SELECT user_id FROM users WHERE email = :1", (email,))
        user_id = cur.fetchone()[0]

        if role == "NGO":
            cur.execute(
                """
                INSERT INTO ngo_profiles
                    (ngo_id, organization_name, address, city, state, pincode, description)
                VALUES (:1, :2, :3, :4, :5, :6, :7)
                """,
                (user_id, name, "", "", "", "", "Created via Google OAuth"),
            )
        else:
            cur.execute(
                """
                INSERT INTO donor_profiles (donor_id, donor_type, organization_name, address)
                VALUES (:1, :2, :3, :4)
                """,
                (user_id, "Individual", name, ""),
            )

        conn.commit()
        return {"user_id": user_id, "role": role, "name": name, "email": email}
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}

    required = ["name", "email", "password", "role", "phone"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f'Field "{field}" is required.'}), 400

    name = data["name"].strip()
    email = data["email"].strip().lower()
    password = data["password"]
    role = data["role"].upper()
    phone = data["phone"].strip()

    if not name or not email or not phone:
        return jsonify({"error": "Name, email, and phone are required."}), 400

    if role not in ("NGO", "DONOR"):
        return jsonify({"error": "Role must be NGO or DONOR."}), 400
    if not validate_email(email):
        return jsonify({"error": "Invalid email format."}), 400
    if not validate_password(password):
        return jsonify(
            {"error": "Password must be at least 8 chars with upper, lower, digit and special character."}
        ), 400
    if not validate_phone(phone):
        return jsonify({"error": "Phone must be exactly 10 digits."}), 400

    if role == "NGO":
        pincode = (data.get("pincode") or "").strip()
        if pincode and not validate_pincode(pincode):
            return jsonify({"error": "Pincode must be 6 digits."}), 400

    conn = get_connection()
    cur = conn.cursor()
    pw_hash = hash_password(password)
    try:
        cur.execute("SELECT user_id FROM users WHERE email = :1", (email,))
        if cur.fetchone():
            return jsonify({"error": "Email already registered."}), 409

        if _phone_in_use(cur, phone):
            return jsonify({"error": "Phone already registered."}), 409

        cur.execute(
            """
            INSERT INTO users (name, email, password, role, phone)
            VALUES (:1, :2, :3, :4, :5)
            """,
            (name, email, pw_hash, role, phone),
        )

        cur.execute("SELECT user_id FROM users WHERE email = :1", (email,))
        user_id = cur.fetchone()[0]

        if role == "NGO":
            cur.execute(
                """
                INSERT INTO ngo_profiles
                    (ngo_id, organization_name, address, city, state, pincode, description)
                VALUES (:1, :2, :3, :4, :5, :6, :7)
                """,
                (
                    user_id,
                    (data.get("organization_name") or name).strip(),
                    (data.get("address") or "").strip(),
                    (data.get("city") or "").strip(),
                    (data.get("state") or "").strip(),
                    (data.get("pincode") or "").strip(),
                    (data.get("description") or "").strip(),
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO donor_profiles (donor_id, donor_type, organization_name, address)
                VALUES (:1, :2, :3, :4)
                """,
                (
                    user_id,
                    (data.get("donor_type") or "Individual").strip(),
                    (data.get("organization_name") or "").strip(),
                    (data.get("address") or "").strip(),
                ),
            )

        conn.commit()
        return jsonify({"message": "Registration successful!", "user_id": user_id}), 201
    except Exception as exc:
        conn.rollback()
        if "ORA-00001" in str(exc):
            return jsonify({"error": "Email or phone already registered."}), 409
        return jsonify({"error": str(exc)}), 500
    finally:
        cur.close()
        conn.close()


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT user_id, name, role
            FROM users
            WHERE email = :1 AND password = :2
            """,
            (email, hash_password(password)),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Invalid credentials."}), 401

        session.pop("driver_id", None)
        session.pop("driver_name", None)
        session.pop("driver_phone", None)
        session["user_id"] = row[0]
        session["role"] = row[2]
        session["name"] = row[1]

        return jsonify(
            {
                "message": "Login successful!",
                "user_id": row[0],
                "name": row[1],
                "role": row[2],
            }
        ), 200
    finally:
        cur.close()
        conn.close()


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully."}), 200


@auth_bp.route("/me", methods=["GET"])
def me():
    user = get_current_user()
    driver = get_current_driver()

    if user:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT user_id, name, email, role, phone, created_at
                FROM users
                WHERE user_id = :1
                """,
                (user["user_id"],),
            )
            row = cur.fetchone()
            if not row:
                session.clear()
                return jsonify({"error": "Session expired."}), 401
            return jsonify(
                {
                    "user_id": row[0],
                    "name": row[1],
                    "email": row[2],
                    "role": row[3],
                    "phone": row[4],
                    "created_at": str(row[5]),
                }
            )
        finally:
            cur.close()
            conn.close()

    if driver:
        return jsonify(
            {
                "driver_id": driver["driver_id"],
                "name": driver["name"],
                "phone": driver["phone"],
                "role": "DRIVER",
            }
        )

    return jsonify({"error": "Not logged in."}), 401


@auth_bp.route("/google/init", methods=["POST"])
def google_auth_init():
    try:
        data = request.get_json() or {}
        role_preference = (data.get("role") or "DONOR").upper()
        if role_preference not in ("NGO", "DONOR"):
            role_preference = "DONOR"

        state = secrets.token_urlsafe(32)
        session["google_oauth_state"] = state
        session["google_oauth_role"] = role_preference
        session.permanent = True

        return jsonify(
            {
                "auth_url": get_google_oauth_url(state),
                "message": "Redirect user to this URL for Google login",
            }
        ), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:
        return jsonify({"error": f"OAuth initialization failed: {exc}"}), 500


@auth_bp.route("/google/callback", methods=["GET"])
def google_auth_callback():
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")

        if error:
            return jsonify({"error": f"Google OAuth error: {error}"}), 400
        if not code or not state:
            return jsonify({"error": "Missing code or state parameter"}), 400
        if session.get("google_oauth_state") != state:
            return jsonify({"error": "Invalid state parameter - possible CSRF attack"}), 400

        token_data = exchange_google_code_for_token(code)
        access_token = token_data.get("access_token")
        if not access_token:
            return jsonify({"error": "Failed to obtain access token"}), 400

        user = get_or_create_user_from_google(get_google_user_info(access_token))
        session.pop("driver_id", None)
        session.pop("driver_name", None)
        session.pop("driver_phone", None)
        session["user_id"] = user["user_id"]
        session["role"] = user["role"]
        session["name"] = user["name"]

        return jsonify(
            {
                "message": "Google login successful!",
                "user_id": user["user_id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
            }
        ), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Google callback failed: {exc}"}), 500
