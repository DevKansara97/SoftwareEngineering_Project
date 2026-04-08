"""
routes/auth.py - Registration & Login
Passwords are hashed with SHA-256 for the academic prototype.
"""

import hashlib
import os
import re
import secrets
import smtplib
import random
from datetime import datetime, timedelta
from email.message import EmailMessage

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


def send_otp_email(receiver_email: str, otp: str):
    """Sends OTP via SMTP and logs to console for debugging."""
    # Load from environment or use placeholders
    sender_email = os.getenv("SMTP_USER", "Bansari1101@gmail.com")
    password = os.getenv("SMTP_PASS", "your-app-password")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    # ALWAYS log to console - this is the "fix" for local development
    print("\n" + "="*50)
    print(f"  [OTP DEBUG]")
    print(f"  Recipient : {receiver_email}")
    print(f"  OTP Code  : {otp}")
    print(f"  Sender    : {sender_email}")
    print("="*50 + "\n")

    # If password is still the placeholder, don't attempt real SMTP
    if not password or password == "your-app-password":
        print("!!! SMTP_PASS not configured in .env. Real email will NOT be sent.")
        print("!!! Please check your .env file or use the [OTP DEBUG] code above.")
        return

    # Plain-text fallback
    plain_text = (
        f"Your Seva Connect Verification Code\n"
        f"{'='*40}\n\n"
        f"Your one-time password (OTP) is: {otp}\n\n"
        f"This code is valid for 2 minutes. Do not share it with anyone.\n"
        f"If you did not request this code, please ignore this email.\n\n"
        f"— Team Seva Connect"
    )

    # Professional HTML email
    html_body = f"""\
    <html>
    <body style="margin:0; padding:0; background-color:#f4f6f9; font-family: 'Segoe UI', Arial, sans-serif;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9; padding:40px 0;">
        <tr>
          <td align="center">
            <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                   style="background:#ffffff; border-radius:12px; box-shadow:0 2px 12px rgba(0,0,0,0.08); overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="background: linear-gradient(135deg, #6366f1, #8b5cf6); padding:32px 40px; text-align:center;">
                  <h1 style="margin:0; color:#ffffff; font-size:24px; font-weight:700; letter-spacing:0.5px;">
                    🙏 Seva Connect
                  </h1>
                  <p style="margin:6px 0 0; color:rgba(255,255,255,0.85); font-size:13px;">
                    Secure Login Verification
                  </p>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:36px 40px 20px;">
                  <p style="margin:0 0 8px; color:#1e293b; font-size:16px; font-weight:600;">
                    Hello,
                  </p>
                  <p style="margin:0 0 24px; color:#475569; font-size:14px; line-height:1.6;">
                    We received a login request for your Seva Connect account. Use the verification code below to complete your sign-in:
                  </p>

                  <!-- OTP Code Block -->
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td align="center" style="padding:8px 0 28px;">
                        <div style="display:inline-block; background:#f0f0ff; border:2px dashed #6366f1; border-radius:10px; padding:18px 48px;">
                          <span style="font-size:36px; font-weight:800; letter-spacing:12px; color:#4f46e5; font-family:'Courier New',monospace;">
                            {otp}
                          </span>
                        </div>
                      </td>
                    </tr>
                  </table>

                  <p style="margin:0 0 20px; color:#64748b; font-size:13px; text-align:center;">
                    ⏱️ This code expires in <strong style="color:#ef4444;">2 minutes</strong>
                  </p>
                </td>
              </tr>

              <!-- Security Note -->
              <tr>
                <td style="padding:0 40px 32px;">
                  <table role="presentation" width="100%" style="background:#fef9ee; border-left:4px solid #f59e0b; border-radius:6px; padding:14px 18px;">
                    <tr>
                      <td>
                        <p style="margin:0; color:#92400e; font-size:12px; line-height:1.5;">
                          🔒 <strong>Security Tip:</strong> Never share this code with anyone. Seva Connect will never ask you for your OTP via phone or message.
                        </p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td style="background:#f8fafc; padding:20px 40px; text-align:center; border-top:1px solid #e2e8f0;">
                  <p style="margin:0 0 4px; color:#94a3b8; font-size:11px;">
                    This is an automated message from Seva Connect.
                  </p>
                  <p style="margin:0; color:#94a3b8; font-size:11px;">
                    If you didn't request this code, you can safely ignore this email.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

    msg = EmailMessage()
    msg["Subject"] = "Your Seva Connect Verification Code"
    msg["From"] = f"Seva Connect <{sender_email}>"
    msg["To"] = receiver_email
    msg.set_content(plain_text)
    msg.add_alternative(html_body, subtype="html")

    try:
        # Use a timeout to prevent hanging the request
        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
            server.set_debuglevel(1)  # Enable verbose SMTP logging in console
            server.starttls()
            server.login(sender_email, password)
            server.send_message(msg)
            print(f"Successfully sent OTP email to {receiver_email}")
    except Exception as e:
        print(f"ERROR: Failed to send email to {receiver_email}: {e}")


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
            SELECT user_id, name, role, email
            FROM users
            WHERE email = :1 AND password = :2
            """,
            (email, hash_password(password)),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Invalid credentials."}), 401

        # Use canonical email from DB
        db_email = row[3]

        # Generate 6-digit OTP
        otp = f"{random.randint(100000, 999999)}"
        expiry = datetime.now() + timedelta(minutes=2)

        # Store in DB
        cur.execute("DELETE FROM login_otp WHERE email = :1", (db_email,))
        cur.execute(
            "INSERT INTO login_otp (email, otp_code, expires_at) VALUES (:1, :2, :3)",
            (db_email, otp, expiry),
        )
        conn.commit()

        # Send Email
        send_otp_email(db_email, otp)

        # Pending session
        session["pending_email"] = db_email

        return jsonify(
            {
                "2fa_required": True,
                "email_sent_to": db_email,
                "expires_in_seconds": 120,
                "message": f"Step 2: A 6-digit code has been sent to {db_email}. Valid for 2 minutes.",
            }
        ), 200
    finally:
        cur.close()
        conn.close()


@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json() or {}
    otp = data.get("otp", "").strip()
    email = session.get("pending_email")

    if not email:
        return jsonify({"error": "Session expired. Please login again."}), 401
    if not otp:
        return jsonify({"error": "OTP is required."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT otp_code, expires_at, attempts FROM login_otp WHERE email = :1",
            (email,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "No OTP found for this email."}), 400

        db_otp, expires_at, attempts = row
        if datetime.now() > expires_at:
            return jsonify({"error": "OTP expired."}), 401

        if attempts >= 3:
            return jsonify({"error": "Maximum attempts reached. Please login again."}), 401

        if db_otp != otp:
            cur.execute(
                "UPDATE login_otp SET attempts = attempts + 1 WHERE email = :1", (email,)
            )
            conn.commit()
            return jsonify({"error": f"Invalid OTP. {2 - attempts} attempts left."}), 401

        # OTP is correct! Fetch user and log in
        cur.execute("SELECT user_id, name, role FROM users WHERE email = :1", (email,))
        user_row = cur.fetchone()

        session.pop("driver_id", None)
        session.pop("driver_name", None)
        session.pop("driver_phone", None)
        session["user_id"] = user_row[0]
        session["role"] = user_row[2]
        session["name"] = user_row[1]
        session.pop("pending_email", None)

        # Cleanup OTP
        cur.execute("DELETE FROM login_otp WHERE email = :1", (email,))
        conn.commit()

        return jsonify(
            {
                "user_id": user_row[0],
                "name": user_row[1],
                "role": user_row[2],
                "message": "Login successful!",
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
