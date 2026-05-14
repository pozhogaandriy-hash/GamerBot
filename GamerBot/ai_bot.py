# ai_bot.py
import discord
from discord.ext import commands
from openai import OpenAI
import os
import json
from dotenv import load_dotenv

load_dotenv()

# ---------------- API KEY ----------------
API_KEY = os.getenv("OPENAI_API_KEY")

# ---------------- OpenAI Client ----------------
client = None

if API_KEY:
    client = OpenAI(
        api_key=API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )

AI_CHANNELS_FILE = "ai_channels.json"

# ---------------- Load channels ----------------
def load_ai_channels():
    if not os.path.exists(AI_CHANNELS_FILE):
        with open(AI_CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

    with open(AI_CHANNELS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------- Save channels ----------------
def save_ai_channels(channels):
    with open(AI_CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=4)

# ---------------- Memory ----------------
conversation_history = {}

# ---------------- AI Channels ----------------
ai_channels = []

# ---------------- Generate AI Response ----------------
async def generate_ai_response(user_id, message):

    if client is None:
        return (
            "❌ OPENAI_API_KEY не знайдено.\n"
            "Добав ключ у Pterodactyl Startup Variables."
        )

    history = conversation_history.get(str(user_id), [])

    history.append({
        "role": "user",
        "content": message
    })

    if len(history) > 10:
        history = history[-10:]

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ти Discord AI бот. "
                        "Відповідай коротко, дружньо, "
                        "українською або англійською."
                    )
                }
            ] + history,
            temperature=0.8,
            max_tokens=300
        )

        reply = completion.choices[0].message.content

        history.append({
            "role": "assistant",
            "content": reply
        })

        conversation_history[str(user_id)] = history

        return reply

    except Exception as e:
        return f"❌ AI Error: {e}"

# ---------------- Check AI channel ----------------
def is_ai_channel(channel_id):
    return channel_id in ai_channels

# ---------------- Setup ----------------
def setup_ai(bot, state=None):

    global ai_channels

    ai_channels = load_ai_channels()

    @bot.tree.command(
        name="setaichannel",
        description="🦾 Встановити AI чат"
    )
    async def setaichannel(interaction: discord.Interaction):

        if interaction.channel_id in ai_channels:
            await interaction.response.send_message(
                "⚠️ AI чат вже встановлений.",
                ephemeral=True
            )
            return

        ai_channels.append(interaction.channel_id)

        save_ai_channels(ai_channels)

        await interaction.response.send_message(
            "✅ AI чат встановлено!"
        )

    @bot.tree.command(
        name="removeaichannel",
        description="Видалити AI чат"
    )
    async def removeaichannel(interaction: discord.Interaction):

        if interaction.channel_id not in ai_channels:
            await interaction.response.send_message(
                "❌ Це не AI чат.",
                ephemeral=True
            )
            return

        ai_channels.remove(interaction.channel_id)

        save_ai_channels(ai_channels)

        await interaction.response.send_message(
            "✅ AI чат видалено."
        )

    @bot.tree.command(
        name="clearai",
        description="Очистити пам'ять AI"
    )
    async def clearai(interaction: discord.Interaction):

        conversation_history.pop(
            str(interaction.user.id),
            None
        )

        await interaction.response.send_message(
            "🧹 AI memory cleared."
        )

    print(f"✅ AI модуль налаштовано. AI канали: {ai_channels}")