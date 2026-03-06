"""
routes/notifications.py  –  Notification read / management
Maps to: NotificationModule, FR-3, FR-12
"""

from flask import Blueprint, request, jsonify
from db import get_connection

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/', methods=['GET'])
def get_notifications():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT notification_id, message, is_read, created_at
            FROM notifications
            WHERE user_id = :1
            ORDER BY created_at DESC
        """, (int(user_id),))
        rows = cur.fetchall()
        return jsonify([{
            'notification_id': r[0],
            'message':   r[1],
            'is_read':   bool(r[2]),
            'created_at': str(r[3])
        } for r in rows])
    finally:
        cur.close()
        conn.close()


@notifications_bp.route('/mark-read', methods=['PUT'])
def mark_read():
    data            = request.get_json()
    notification_id = data.get('notification_id')
    user_id         = data.get('user_id')

    conn = get_connection()
    cur  = conn.cursor()
    try:
        if notification_id:
            cur.execute("""
                UPDATE notifications SET is_read = 1
                WHERE notification_id = :1
            """, (int(notification_id),))
        elif user_id:
            cur.execute("""
                UPDATE notifications SET is_read = 1
                WHERE user_id = :1
            """, (int(user_id),))
        conn.commit()
        return jsonify({'message': 'Marked as read.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


@notifications_bp.route('/unread-count', methods=['GET'])
def unread_count():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*) FROM notifications
            WHERE user_id = :1 AND is_read = 0
        """, (int(user_id),))
        count = cur.fetchone()[0]
        return jsonify({'unread_count': count})
    finally:
        cur.close()
        conn.close()
