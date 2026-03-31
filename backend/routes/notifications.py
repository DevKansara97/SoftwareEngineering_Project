"""
routes/notifications.py - Notification read / management
"""

from flask import Blueprint, jsonify, request

from access import get_current_user
from db import get_connection

notifications_bp = Blueprint("notifications", __name__)


def _require_user():
    user = get_current_user()
    if not user:
        return None, (jsonify({"error": "Login required."}), 401)
    return user, None


@notifications_bp.route("/", methods=["GET"])
def get_notifications():
    user, error = _require_user()
    if error:
        return error

    user_id = request.args.get("user_id", type=int) or user["user_id"]
    if user_id != user["user_id"]:
        return jsonify({"error": "You can only view your own notifications."}), 403

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT notification_id, message, is_read, created_at
            FROM notifications
            WHERE user_id = :1
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        return jsonify(
            [
                {
                    "notification_id": row[0],
                    "message": row[1],
                    "is_read": bool(row[2]),
                    "created_at": str(row[3]),
                }
                for row in rows
            ]
        )
    finally:
        cur.close()
        conn.close()


@notifications_bp.route("/mark-read", methods=["PUT"])
def mark_read():
    user, error = _require_user()
    if error:
        return error

    data = request.get_json() or {}
    notification_id = data.get("notification_id")
    user_id = data.get("user_id")

    conn = get_connection()
    cur = conn.cursor()
    try:
        if notification_id:
            cur.execute(
                """
                UPDATE notifications
                SET is_read = 1
                WHERE notification_id = :1 AND user_id = :2
                """,
                (int(notification_id), user["user_id"]),
            )
        else:
            target_user_id = int(user_id or user["user_id"])
            if target_user_id != user["user_id"]:
                return jsonify({"error": "You can only update your own notifications."}), 403
            cur.execute(
                """
                UPDATE notifications
                SET is_read = 1
                WHERE user_id = :1
                """,
                (target_user_id,),
            )
        conn.commit()
        return jsonify({"message": "Marked as read."})
    except Exception as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        cur.close()
        conn.close()


@notifications_bp.route("/unread-count", methods=["GET"])
def unread_count():
    user, error = _require_user()
    if error:
        return error

    user_id = request.args.get("user_id", type=int) or user["user_id"]
    if user_id != user["user_id"]:
        return jsonify({"error": "You can only view your own notifications."}), 403

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM notifications
            WHERE user_id = :1 AND is_read = 0
            """,
            (user_id,),
        )
        return jsonify({"unread_count": cur.fetchone()[0]})
    finally:
        cur.close()
        conn.close()
