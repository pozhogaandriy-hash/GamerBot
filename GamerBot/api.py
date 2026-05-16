#api.py
import os
from flask import Blueprint, request, session, jsonify
from premium import is_premium, add_premium, get_all_premium_users

api = Blueprint("api", __name__)

API_KEY = os.getenv("API_KEY")

# Функцію для DM будемо імпортувати пізніше (з main.py)
send_premium_dm_callback = None

def set_dm_callback(callback):
    global send_premium_dm_callback
    send_premium_dm_callback = callback

@api.route("/me", methods=["GET"])
def me():
    discord_id = session.get("discord_id")
    
    if not discord_id:
        return jsonify({
            "logged_in": False,
            "discord_id": None,
            "username": None,
            "avatar_url": None,
            "premium": False
        })
    
    return jsonify({
        "logged_in": True,
        "discord_id": discord_id,
        "username": session.get("username", "Unknown"),
        "avatar_url": session.get("avatar_url"),
        "premium": is_premium(discord_id)
    })

@api.route("/logout", methods=["POST"])
def logout_endpoint():
    session.pop("discord_id", None)
    session.pop("username", None)
    return jsonify({"success": True})

@api.route("/activate-premium", methods=["POST"])
def activate_premium():
    auth = request.headers.get("Authorization")
    
    if auth != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    discord_id = data.get("discordId")
    source = data.get("source", "api")
    
    if not discord_id:
        return jsonify({"error": "No discord ID"}), 400
    
    add_premium(discord_id, source=source)
    
    # Відправляємо DM, якщо callback встановлено
    if send_premium_dm_callback:
        send_premium_dm_callback(discord_id)
    
    return jsonify({
        "success": True,
        "discord_id": discord_id,
        "premium": True
    })

@api.route("/check-premium", methods=["GET"])
def check_premium():
    discord_id = request.args.get("discordId")
    
    if not discord_id:
        return jsonify({"error": "Missing discordId"}), 400
    
    return jsonify({
        "discord_id": discord_id,
        "premium": is_premium(discord_id)
    })

@api.route("/premium-users", methods=["GET"])
def premium_users():
    auth = request.headers.get("Authorization")
    
    if auth != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    users = get_all_premium_users()
    return jsonify({"premium_users": users})
