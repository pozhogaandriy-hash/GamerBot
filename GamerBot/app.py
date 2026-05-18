import os
import stripe
from flask import Flask, session, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

# Завантаження змінних середовища
load_dotenv()

# Імпорт blueprint
from discord_auth import discord_auth


# Ініціалізація Flask
app = Flask(__name__)

# ========== КЛЮЧОВА КОНФІГУРАЦІЯ ДЛЯ SESSION COOKIE ==========
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "gamerbot123")

# Налаштування session cookie для cross-site роботи
app.config["SESSION_COOKIE_SAMESITE"] = "None"      # Дозволяє cross-site
app.config["SESSION_COOKIE_SECURE"] = True          # Обов'язково для SameSite=None
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_DOMAIN"] = None          # Автоматично

# Додаткові налаштування
app.config["SESSION_PERMANENT"] = False
app.config["PERMANENT_SESSION_LIFETIME"] = 3600     # 1 година

# ========== CORS НАЛАШТУВАННЯ ==========
CORS(app, 
     origins=[
         "https://gamerbot.kite.space",
         "http://gamerbot.kite.space",
         "http://80.75.218.33:25572",  # для тестування
         "http://localhost:3000"        # для локального тестування
     ],
     supports_credentials=True,         # Дозволяє cookies
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# ========== API КЛЮЧ ДЛЯ ПЕРЕВІРКИ ==========
API_KEY = os.getenv("API_KEY")

# ========== ФУНКЦІЇ PREMIUM ==========
from premium import is_premium, add_premium, get_all_premium_users

# Callback для DM (встановлюється з main.py)
send_premium_dm_callback = None

def set_dm_callback(callback):
    global send_premium_dm_callback
    send_premium_dm_callback = callback

# ========== API ROUTES ==========

@app.route("/", methods=["GET"])
def home():
    return {
        "status": "API is running",
        "version": "1.0.0",
        "endpoints": [
            "/me",
            "/logout",
            "/activate-premium",
            "/check-premium",
            "/premium-users",
            "/auth/discord/start",
            "/auth/discord/callback",
            "/auth/discord/logout",
            "/stripe/create-checkout-session",
            "/stripe/webhook"
        ]
    }

@app.route("/me", methods=["GET"])
def me():
    discord_id = session.get("discord_id")
    
    if not discord_id:
        return jsonify({
            "logged_in": False,
            "discord_id": None,
            "username": None,
            "premium": False
        })
    
    return jsonify({
        "logged_in": True,
        "discord_id": discord_id,
        "username": session.get("username", "Unknown"),
        "premium": is_premium(discord_id)
    })

@app.route("/logout", methods=["POST", "GET"])
def logout_endpoint():
    session.pop("discord_id", None)
    session.pop("username", None)
    return jsonify({"success": True, "message": "Logged out"})

@app.route("/activate-premium", methods=["POST"])
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

@app.route("/check-premium", methods=["GET"])
def check_premium():
    discord_id = request.args.get("discordId")
    
    if not discord_id:
        return jsonify({"error": "Missing discordId"}), 400
    
    return jsonify({
        "discord_id": discord_id,
        "premium": is_premium(discord_id)
    })

@app.route("/premium-users", methods=["GET"])
def premium_users():
    auth = request.headers.get("Authorization")
    
    if auth != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    users = get_all_premium_users()
    return jsonify({"premium_users": users})

# ========== STRIPE ROUTES ==========

@app.route("/stripe/create-checkout-session", methods=["POST"])
def create_checkout_session():
    discord_id = session.get("discord_id")
    
    if not discord_id:
        return jsonify({"error": "Not logged in"}), 401
    
    STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "https://gamerbot.kite.space")
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    
    if not STRIPE_PRICE_ID:
        return jsonify({"error": "Stripe price ID not configured"}), 500
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price": STRIPE_PRICE_ID,
                "quantity": 1,
            }],
            mode="payment",
            allow_promotion_codes=True,
            success_url=f"{FRONTEND_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/payment-cancel",
            metadata={
                "discord_id": discord_id
            }
        )
        
        return jsonify({"url": checkout_session.url})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")
    
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    
    if not STRIPE_WEBHOOK_SECRET:
        print("[ERROR] STRIPE_WEBHOOK_SECRET not set")
        return jsonify({"error": "Webhook secret not configured"}), 500
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        print(f"[ERROR] Invalid payload: {e}")
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError as e:
        print(f"[ERROR] Invalid signature: {e}")
        return jsonify({"error": "Invalid signature"}), 400
    
    # Отримуємо тип події (ТУТ визначаємо event_type)
    event_type = event["type"]
    print(f"[DEBUG] Event type: {event_type}")
    
    if event_type == "checkout.session.completed":
        print("[DEBUG] Checkout session completed!")
        
        # Отримуємо session об'єкт
        session_obj = event["data"]["object"]
        
        # Отримуємо discord_id з metadata
        try:
            if hasattr(session_obj, 'to_dict'):
                session_dict = session_obj.to_dict()
            else:
                session_dict = session_obj
            
            metadata = session_dict.get("metadata", {})
            discord_id = metadata.get("discord_id")
            print(f"[DEBUG] Discord ID from metadata: {discord_id}")
            
            if discord_id:
                add_premium(discord_id, source="stripe")
                print(f"[STRIPE] ✅ Premium activated for {discord_id}")
                
                if send_premium_dm_callback:
                    send_premium_dm_callback(discord_id)
            else:
                print("[WARNING] No discord_id in metadata")
        except Exception as e:
            print(f"[ERROR] Failed to extract discord_id: {e}")
            import traceback
            traceback.print_exc()
    
    return jsonify({"success": True})
# ========== РЕЄСТРАЦІЯ BLUEPRINT ==========
app.register_blueprint(discord_auth)

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    port = int(os.getenv("PORT", 25572))
    app.run(host="0.0.0.0", port=port, debug=True)
