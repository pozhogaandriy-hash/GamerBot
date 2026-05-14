import os
import requests
from flask import Blueprint, redirect, request, session

discord_auth = Blueprint("discord_auth", __name__)

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

@discord_auth.route("/auth/discord/start")
def discord_login():
    url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=identify"
    )
    return redirect(url)

@discord_auth.route("/auth/discord/callback")
def discord_callback():
    code = request.args.get("code")
    error = request.args.get("error")
    
    if error:
        return redirect(f"{FRONTEND_URL}/login?error=discord_denied")
    
    if not code:
        return redirect(f"{FRONTEND_URL}/login?error=no_code")
    
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    r = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    
    if r.status_code != 200:
        return redirect(f"{FRONTEND_URL}/login?error=token_failed")
    
    token_data = r.json()
    
    if "access_token" not in token_data:
        return redirect(f"{FRONTEND_URL}/login?error=no_token")
    
    user = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"}
    ).json()
    
    if not user.get("id"):
        return redirect(f"{FRONTEND_URL}/login?error=no_user")
    
    session["discord_id"] = user["id"]
    session["username"] = user.get("username", "Unknown")
    
    return redirect(f"{FRONTEND_URL}/?login=success")

@discord_auth.route("/auth/discord/logout")
def logout():
    session.pop("discord_id", None)
    session.pop("username", None)
    return redirect(f"{FRONTEND_URL}/")