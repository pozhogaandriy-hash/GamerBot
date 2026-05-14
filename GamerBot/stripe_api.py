import os
import stripe
from flask import Blueprint, request, jsonify, session
from premium import add_premium

stripe_api = Blueprint("stripe_api", __name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Callback для DM
send_premium_dm_callback = None

def set_dm_callback(callback):
    global send_premium_dm_callback
    send_premium_dm_callback = callback

@stripe_api.route("/stripe/create-checkout-session", methods=["POST"])
def create_checkout_session():
    discord_id = session.get("discord_id")
    
    if not discord_id:
        return jsonify({"error": "Not logged in"}), 401
    
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
            success_url=f"{FRONTEND_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/payment-cancel",
            metadata={
                "discord_id": discord_id
            }
        )
        
        return jsonify({"url": checkout_session.url})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stripe_api.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")
    
    if not STRIPE_WEBHOOK_SECRET:
        return jsonify({"error": "Webhook secret not configured"}), 500
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400
    
    if event["type"] == "checkout.session.completed":
        session_obj = event["data"]["object"]
        discord_id = session_obj.get("metadata", {}).get("discord_id")
        
        if discord_id:
            add_premium(discord_id, source="stripe")
            print(f"[STRIPE] Premium activated for {discord_id}")
            
            # Відправляємо DM
            if send_premium_dm_callback:
                send_premium_dm_callback(discord_id)
    
    return jsonify({"success": True})