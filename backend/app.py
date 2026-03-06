"""
Seva Connect - NGO Resource & Donation Management System
Main Flask Application Entry Point
Framework: Python Flask + Oracle DB (oracledb)
"""

import sys, os

# ── Path setup ────────────────────────────────────────────────────────────────
# BASE_DIR    = the backend/ folder  (e.g. E:\CSE408\SevaConnect\backend)
# PROJECT_DIR = the seva-connect/ root (one level up from backend/)
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

# Put backend/ on sys.path so 'db' and 'routes' are always importable
sys.path.insert(0, BASE_DIR)

TEMPLATE_DIR = os.path.join(PROJECT_DIR, 'frontend', 'templates')
STATIC_DIR   = os.path.join(PROJECT_DIR, 'frontend', 'static')

from flask import Flask, render_template, session
from flask_cors import CORS
from routes.auth import auth_bp
from routes.ngo import ngo_bp
from routes.donor import donor_bp
from routes.requirements import requirements_bp
from routes.donations import donations_bp
from routes.delivery import delivery_bp
from routes.notifications import notifications_bp
from routes.search import search_bp
from db import init_db

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = 'seva_connect_secret_key_2024'
CORS(app)

# Register Blueprints
app.register_blueprint(auth_bp,          url_prefix='/api/auth')
app.register_blueprint(ngo_bp,           url_prefix='/api/ngo')
app.register_blueprint(donor_bp,         url_prefix='/api/donor')
app.register_blueprint(requirements_bp,  url_prefix='/api/requirements')
app.register_blueprint(donations_bp,     url_prefix='/api/donations')
app.register_blueprint(delivery_bp,      url_prefix='/api/delivery')
app.register_blueprint(notifications_bp, url_prefix='/api/notifications')
app.register_blueprint(search_bp,        url_prefix='/api/search')

# ── Page routes ───────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/ngo/dashboard')
def ngo_dashboard():
    return render_template('ngo_dashboard.html')

@app.route('/donor/dashboard')
def donor_dashboard():
    return render_template('donor_dashboard.html')

@app.route('/ngo/requirements')
def ngo_requirements():
    return render_template('ngo_requirements.html')

@app.route('/donor/search')
def donor_search():
    return render_template('donor_search.html')

@app.route('/donor/donate/<int:requirement_id>')
def donate_page(requirement_id):
    return render_template('donate.html', requirement_id=requirement_id)

@app.route('/tracking/<int:order_id>')
def tracking_page(order_id):
    return render_template('tracking.html', order_id=order_id)

@app.route('/notifications')
def notifications_page():
    return render_template('notifications.html')

# ── Debug helper: print resolved paths on startup ────────────────────────────
def _print_paths():
    print(f"  BASE_DIR     : {BASE_DIR}")
    print(f"  PROJECT_DIR  : {PROJECT_DIR}")
    print(f"  TEMPLATE_DIR : {TEMPLATE_DIR}  (exists={os.path.isdir(TEMPLATE_DIR)})")
    print(f"  STATIC_DIR   : {STATIC_DIR}  (exists={os.path.isdir(STATIC_DIR)})")

if __name__ == '__main__':
    print("Initializing database tables...")
    init_db()
    print("Resolved paths:")
    _print_paths()
    print("Starting Seva Connect server on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)