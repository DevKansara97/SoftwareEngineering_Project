"""
Shared session and access helpers for Seva Connect routes.
"""

from flask import session


def get_current_user():
    user_id = session.get("user_id")
    role = session.get("role")
    if not user_id or not role:
        return None
    return {
        "user_id": int(user_id),
        "role": role,
        "name": session.get("name"),
    }


def get_current_driver():
    driver_id = session.get("driver_id")
    if not driver_id:
        return None
    return {
        "driver_id": int(driver_id),
        "name": session.get("driver_name"),
        "phone": session.get("driver_phone"),
    }
