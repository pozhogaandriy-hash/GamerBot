import json
import os
from datetime import datetime

PREMIUM_FILE = "premium.json"

def load_premium():
    if not os.path.exists(PREMIUM_FILE):
        with open(PREMIUM_FILE, "w") as f:
            json.dump({}, f)
    with open(PREMIUM_FILE, "r") as f:
        return json.load(f)

def save_premium(data):
    with open(PREMIUM_FILE, "w") as f:
        json.dump(data, f, indent=4)

def add_premium(discord_id, source="stripe"):
    data = load_premium()
    data[str(discord_id)] = {
        "premium": True,
        "activated_at": datetime.utcnow().isoformat(),
        "source": source
    }
    save_premium(data)
    return True

def is_premium(discord_id):
    data = load_premium()
    user = data.get(str(discord_id))
    if not user:
        return False
    return user.get("premium", False)

def remove_premium(discord_id):
    data = load_premium()
    if str(discord_id) in data:
        del data[str(discord_id)]
        save_premium(data)
        return True
    return False

def get_all_premium_users():
    data = load_premium()
    return [int(uid) for uid, info in data.items() if info.get("premium")]