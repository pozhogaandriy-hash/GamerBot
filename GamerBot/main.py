# main.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import logging
from flask import Flask, request, session
import threading
from dotenv import load_dotenv
from itertools import cycle
from discord.ext import tasks
from ai_bot import setup_ai, is_ai_channel, generate_ai_response
from premium import add_premium, is_premium  
from discord_auth import discord_auth
#-------------config message cache----------------
count_message_cache = {}

# ---------------- Config ----------------
load_dotenv()
TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY") 
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET")
app.register_blueprint(discord_auth)

STATE_FILE = "state.json"
LOG_FILE = "bot.log"
SUPPORT_FILE = "support.txt"

UKRAINIAN_FILE = "ukrainian.txt"
ENGLISH_FILE = "english.txt"

SERVERS_DIR = "servers"
GAME_LOGS_DIR = "game_logs"

# ---------------- Logging ----------------
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("=== bot.log ===\n")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ---------------- Status cycle ----------------
status_cycle = cycle([
    lambda: discord.Game(name="/help"),
    lambda: discord.Activity(
        type=discord.ActivityType.watching,
        name=lambda: f"{len(bot.guilds)} servers"
    ),
])

# ---------------- Load dictionaries ----------------
def load_words(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return set(w.strip().lower() for w in f if w.strip())
        except Exception as e:
            logging.error(f"Cannot load words from {path}: {e}")
            return set()
    else:
        logging.warning(f"Dictionary file not found: {path}")
        return set()

UKRAINIAN_WORDS = load_words(UKRAINIAN_FILE)
ENGLISH_WORDS = load_words(ENGLISH_FILE)
logging.info(f"Loaded dictionaries — UA: {len(UKRAINIAN_WORDS)} words, EN: {len(ENGLISH_WORDS)} words")

# ---------------- Intents & Bot ----------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Імпортуємо ігри з окремих файлів

from rps_game import setup_rps_game
from sendmessage import setup_sendmessage  


# ---------------- State helpers ----------------
def safe_load_state():
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error reading {STATE_FILE}: {e}")
        return {}

def safe_save_state(s):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving {STATE_FILE}: {e}")

state = safe_load_state()

def get_language(gid):
    gid = str(gid)
    if gid in state:
        return state[gid].get("language", "uk")
    return "uk"

def ensure_guild(gid: str):
    """Ensure guild exists in state with all game data"""
    if gid not in state:
        state[gid] = {
            "language": "uk",
            "word_channel": None,
            "count_channel": None,
            "word_data": {
                "last_word": "",
                "last_user": "",
                "used_words": [],
                "top": {}
            },
            "count_data": {
                "last_number": 0,
                "last_user": "",
                "top": {}
            },
            "rps_data": {  
                "top": {}
            }
        }
        safe_save_state(state)
    elif "rps_data" not in state[gid]:  
        state[gid]["rps_data"] = {"top": {}}
        safe_save_state(state)

def ensure_servers_dir():
    if not os.path.exists(SERVERS_DIR):
        os.makedirs(SERVERS_DIR)

def server_file_path(guild_id: str):
    return os.path.join(SERVERS_DIR, f"{guild_id}.json")

def create_server_file(guild: discord.Guild):
    ensure_servers_dir()
    path = server_file_path(str(guild.id))

    lang = state.get(str(guild.id), {}).get("language", "uk")

    data = {
        "id": str(guild.id),
        "name": guild.name,
        "owner_id": str(guild.owner_id) if guild.owner_id else None,
        "language": lang  
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    logging.info(f"[SERVER FILE] Updated {path}")

def delete_server_file(guild_id: str):
    path = server_file_path(str(guild_id))
    if os.path.exists(path):
        os.remove(path)
        logging.info(f"[SERVER FILE] Deleted {path}")

def ensure_game_logs_dir():
    if not os.path.exists(GAME_LOGS_DIR):
        os.makedirs(GAME_LOGS_DIR)

def game_log_path(guild_id: str):
    ensure_game_logs_dir()
    return os.path.join(GAME_LOGS_DIR, f"{guild_id}.txt")

def write_game_log(gid: str, text: str):
    log_dir = f"logs/{gid}"
    os.makedirs(log_dir, exist_ok=True)

    guild = bot.get_guild(int(gid))
    guild_name = guild.name if guild else "Unknown Server"

    with open(f"{log_dir}/games.log", "a", encoding="utf-8") as f:
        f.write(f"[{guild_name}] {text}\n")

# translation helper
def t(gid: str, ua: str, en: str) -> str:
    gid = str(gid) if gid is not None else ""
    lang = state.get(gid, {}).get("language", "uk")
    return ua if lang == "uk" else en

# helper: get last meaningful letter (skip soft sign and similar)
SKIP_LAST = {"ь", "ъ", "ʼ", "’", "и", } 
def get_last_meaningful_letter(word: str) -> str:
    if not word:
        return ""
    for ch in reversed(word):
        if ch not in SKIP_LAST:
            return ch
    return word[-1]

# ---------------- Startup ----------------
@bot.event
async def on_ready():
    # Налаштовуємо всі ігри та команди
    
    setup_rps_game(bot, state)
    setup_sendmessage(bot, state) 
    setup_ai(bot, state)
   
    
    try:
        await bot.tree.sync()
    except Exception as e:
        logging.warning(f"Sync error: {e}")
    logging.info(f"✅ Logged in as {bot.user} ({bot.user.id})")
    logging.info(f"🔧 Registered commands: {len(bot.tree.get_commands())}")

    if not rotate_status.is_running():
        rotate_status.start()

    # ensure state entries for current guilds
    for g in bot.guilds:
        ensure_guild(str(g.id))
        create_server_file(g)

    check_server_files.start()
        # Запускаємо перевірку premium
    if not check_new_premium_users.is_running():
        check_new_premium_users.start()
        logging.info("🔄 Premium checker started (every 10 seconds)")

@bot.event
async def on_guild_join(guild: discord.Guild):
    ensure_guild(str(guild.id))
    create_server_file(guild)

@bot.event
async def on_guild_remove(guild: discord.Guild):
    delete_server_file(str(guild.id))

@tasks.loop(seconds=10)
async def rotate_status():
    activity_factory = next(status_cycle)
    activity = activity_factory()

    # fix for lambda inside name
    if callable(activity.name):
        activity.name = activity.name()

    await bot.change_presence(activity=activity)

@tasks.loop(seconds=20)
async def check_server_files():
    ensure_servers_dir()
    for g in list(bot.guilds):
        path = server_file_path(str(g.id))
        if not os.path.exists(path):
            logging.warning(f"[SECURITY] Server file missing for {g.name}, leaving guild")
            try:
                await g.leave()
            except Exception as e:
                logging.error(f"Failed to leave guild {g.id}: {e}")

# ---------------- Commands ----------------
@bot.tree.command(name="set_word", description="📚 Set channel for the Word game")
@app_commands.describe(channel="Text channel to host the word game")
async def set_word(interaction: discord.Interaction, channel: discord.TextChannel):
    gid = str(interaction.guild.id)
    ensure_guild(gid)
    if not (interaction.user.guild_permissions.manage_channels or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message(t(gid, "🚫 Треба право керувати каналами або Адмін.", "🚫 You need Manage Channels or Administrator."), ephemeral=True)
        return
    state[gid]["word_channel"] = channel.id
    safe_save_state(state)
    await interaction.response.send_message(t(gid, f"✅ Канал для гри 'Слова' встановлено: {channel.mention}", f"✅ Word game channel set: {channel.mention}"), ephemeral=True)
    logging.info(f"[{interaction.guild.name}] Word channel set to {channel.name} by {interaction.user}")

@bot.tree.command(name="set_count", description="🔢 Set channel for the Counting game")
@app_commands.describe(channel="Text channel to host the counting game")
async def set_count(interaction: discord.Interaction, channel: discord.TextChannel):
    gid = str(interaction.guild.id)
    ensure_guild(gid)
    if not (interaction.user.guild_permissions.manage_channels or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message(t(gid, "🚫 Треба право керувати каналами або Адмін.", "🚫 You need Manage Channels or Administrator."), ephemeral=True)
        return
    state[gid]["count_channel"] = channel.id
    safe_save_state(state)
    await interaction.response.send_message(t(gid, f"✅ Канал для гри 'Лічильник' встановлено: {channel.mention}", f"✅ Counting game channel set: {channel.mention}"), ephemeral=True)
    logging.info(f"[{interaction.guild.name}] Count channel set to {channel.name} by {interaction.user}")

@bot.tree.command(name="set_language", description="🌐 Set server language (ukrainian or english)")
@app_commands.describe(language="Choose language for this server")
@app_commands.choices(language=[
    app_commands.Choice(name="Українська 🇺🇦", value="uk"),
    app_commands.Choice(name="English 🇬🇧", value="en"),
])
async def set_language(interaction: discord.Interaction, language: app_commands.Choice[str]):
    gid = str(interaction.guild.id)
    ensure_guild(gid)
    if not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message(t(gid, "🚫 Потрібні права Керувати сервером або Адмін.", "🚫 You need Manage Server or Administrator."), ephemeral=True)
        return
    state[gid]["language"] = language.value
    safe_save_state(state)
    create_server_file(interaction.guild)
    await interaction.response.send_message(t(gid, "✅ Мову встановлено: Українська.", "✅ Language set: English." ) if language.value == "uk" else t(gid, "✅ Мову встановлено: Українська.", "✅ Language set: English."), ephemeral=True)

from discord.ui import View, Button

@bot.tree.command(name="help", description="Show bot help menu")
async def help_cmd(interaction: discord.Interaction):
    gid = str(interaction.guild_id)
    ensure_guild(gid)
    lang = get_language(gid)
    
    class HelpView(View):
        def __init__(self):
            super().__init__(timeout=120)
            self.current_page = 0
            
        async def update_message(self, interaction: discord.Interaction):
            embed = await self.get_page_embed(interaction, self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
        
        async def get_page_embed(self, interaction: discord.Interaction, page: int):
            gid = str(interaction.guild_id)
            lang = get_language(gid)
            
            if page == 0:  # Головна сторінка
                if lang == "uk":
                    embed = discord.Embed(
                        title="📘 **Допомога - Головне меню**",
                        description="Вітаю! Я бот з різноманітними іграми та функціями.\n\n"
                                  "**📋 Навігація:**\n"
                                  "Використовуйте кнопки внизу для переходу між сторінками.\n\n"
                                  "**🎮 Доступні сторінки:**\n"
                                  "• **Сторінка 1** — Ігри\n"
                                  "• **Сторінка 2** — Системні функції\n"
                                  "• **Сторінка 3** — Інформація про бота\n"
                                  "• **Сторінка 4** — Посилання",
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text="Використовуйте кнопки для навігації")
                else:
                    embed = discord.Embed(
                        title="📘 **Help - Main Menu**",
                        description="Hello! I'm a bot with various games and features.\n\n"
                                  "**📋 Navigation:**\n"
                                  "Use the buttons below to navigate between pages.\n\n"
                                  "**🎮 Available pages:**\n"
                                  "• **Page 1** — Games\n"
                                  "• **Page 2** — System features\n"
                                  "• **Page 3** — Bot info\n"
                                  "• **Page 4** — Links",
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text="Use buttons for navigation")
                    
            elif page == 1:  # Ігри
                if lang == "uk":
                    embed = discord.Embed(
                        title="🎮 **Ігри**",
                        description="Ось усі доступні ігри в боті:",
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="📝 **Гра в Слова**",
                        value="Грайте в слова українською або англійською!\n"
                              "• Перевірка словника\n"
                              "• Без повторень\n"
                              "• Нарахування балів\n"
                              "⚙️ Налаштування: `/set_word`\n",
                        inline=False
                    )
                    embed.add_field(
                        name="🔢 **Лічильник**",
                        value="Рахуйте по черзі без помилок!\n"
                              "• Перевірка порядку чисел\n"
                              "• Нарахування балів\n"
                              "⚙️ Налаштування: `/set_count`\n",
                        inline=False
                    )
                    embed.add_field(
                        name="🎮 **Камінь-Ножиці-Папір**",
                        value="Класична гра з системою балів!\n"
                              "• 🪨 `/g_rock` — Камінь\n"
                              "• 📄 `/g_paper` — Папір\n"
                              "• ✂️ `/g_scissors` — Ножиці\n"
                              "• 📊 `/g_points` — Перегляд балів\n"
                              "• 🏆 +10 за перемогу, +2 за нічию, -10 за поразку\n",
                        inline=False
                    )
                else:
                    embed = discord.Embed(
                        title="🎮 **Games**",
                        description="Here are all available games in the bot:",
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="📝 **Word Game**",
                        value="Play words in Ukrainian or English!\n"
                              "• Dictionary check\n"
                              "• No duplicates\n"
                              "• Points system\n"
                              "⚙️ Setup: `/set_word`\n",
                        inline=False
                    )
                    embed.add_field(
                        name="🔢 **Counter**",
                        value="Count in order without mistakes!\n"
                              "• Number order check\n"
                              "• Points system\n"
                              "⚙️ Setup: `/set_count`\n",
                        inline=False
                    )
                    embed.add_field(
                        name="🎮 **Rock-Paper-Scissors**",
                        value="Classic game with points system!\n"
                              "• 🪨 `/g_rock` — Rock\n"
                              "• 📄 `/g_paper` — Paper\n"
                              "• ✂️ `/g_scissors` — Scissors\n"
                              "• 📊 `/g_points` — View points\n"
                              "• 🏆 +10 for win, +2 for draw, -10 for loss\n",
                        inline=False

                    )
                    
            elif page == 2:  # Системні функції
                if lang == "uk":
                    embed = discord.Embed(
                        title="⚙️ **Системні функції**",
                        description="Налаштування та корисні команди:",
                        color=discord.Color.purple()
                    )
                    embed.add_field(
                        name="🌐 **Мова**",
                        value="Змініть мову бота на сервері:\n"
                              "`/set_language`\n"
                              "Доступно: Українська 🇺🇦, English 🇬🇧\n",
                        inline=False
                    )
                    embed.add_field(
                        name="📊 **Топи та бали**",
                        value="• `/top` — Топ гравців на сервері\n"
                              "• `/g_points` — Ваші бали в RPS\n",
                        inline=False
                    )
                    embed.add_field(
                        name="🔄 **Керування**",
                        value="• `/reset` — Скинути ігри (топи зберігаються)\n"
                              "• `/reset_rps` — Скинути бали RPS (адміни)\n"
                              "• `/servers` — Кількість серверів з ботом\n",
                        inline=False
                    )
                else:
                    embed = discord.Embed(
                        title="⚙️ **System Features**",
                        description="Settings and useful commands:",
                        color=discord.Color.purple()
                    )
                    embed.add_field(
                        name="🌐 **Language**",
                        value="Change bot language on server:\n"
                              "`/set_language`\n"
                              "Available: Українська 🇺🇦, English 🇬🇧\n",
                        inline=False
                    )
                    embed.add_field(
                        name="📊 **Tops & Points**",
                        value="• `/top` — Server top players\n"
                              "• `/g_points` — Your RPS points\n",
                        inline=False
                    )
                    embed.add_field(
                        name="🔄 **Management**",
                        value="• `/reset` — Reset games (tops preserved)\n"
                              "• `/reset_rps` — Reset RPS points (admins)\n"
                              "• `/servers` — Number of servers with bot\n",
                        inline=False
                    )
                    embed.add_field(
                        name="📢 **Broadcast**",
                        value="`!sendmessage` — Broadcast message (owner only)\n",
                        inline=False
                    )
                    
            elif page == 3:  # Інформація
                if lang == "uk":
                    embed = discord.Embed(
                        title="ℹ️ **Інформація про бота**",
                        description="Детальна інформація про бота:",
                        color=discord.Color.teal()
                    )
                    embed.add_field(
                        name="🤖 **Про бота**",
                        value="Бот для ігор та розваг на вашому сервері Discord!\n• Ігри в слова\n• Лічильник\n• Камінь-Ножиці-Папір\n",
                        inline=False
                    )
                    embed.add_field(
                        name="💡 **Поради**",
                        value="• Налаштуйте канали для ігор командами `/set_word` та `/set_count`\n"
                              "• Переглядайте топ гравців через `/top`\n"
                              "• Змагайтеся з друзями в RPS!\n",
                        inline=False
                    )
                    embed.add_field(
                        name="📈 **Статистика**",
                        value=f"• Серверів: **{len(bot.guilds)}**\n"
                              f"• Користувачів: **{sum(g.member_count for g in bot.guilds)}**\n"
                              f"• Команд: **{len(bot.tree.get_commands())}**\n",
                        inline=False
                    )
                else:
                    embed = discord.Embed(
                        title="ℹ️ **Bot Info**",
                        description="Detailed information about the bot:",
                        color=discord.Color.teal()
                    )
                    embed.add_field(
                        name="🤖 **About Bot**",
                        value="A bot for games and entertainment on your Discord server!\n"
                              "• Word games\n"
                              "• Counter\n"
                              "• Rock-Paper-Scissors\n",
                        inline=False
                    )
                    embed.add_field(
                        name="💡 **Tips**",
                        value="• Set up game channels with `/set_word` and `/set_count`\n"
                              "• View top players with `/top`\n"
                              "• Compete with friends in RPS!\n",
                        inline=False
                    )
                    embed.add_field(
                        name="📈 **Statistics**",
                        value=f"• Servers: **{len(bot.guilds)}**\n"
                              f"• Users: **{sum(g.member_count for g in bot.guilds)}**\n"
                              f"• Commands: **{len(bot.tree.get_commands())}**\n",
                        inline=False
                    )
                    
            elif page == 4:  # Посилання
                if lang == "uk":
                    embed = discord.Embed(
                        title="🔗 **Корисні посилання**",
                        description="Наш дс сервер: https://discord.gg/AWAUy36Mcj\n" \
                        "Наш сайт : https://gamerbot.mystrikingly.com\n" \
                        "Добавити бота : https://discord.com/oauth2/authorize?client_id=1419270139173404782&permissions=2252627166079169&integration_type=0&scope=bot",
                        color=discord.Color.yellow()
                    )
                else:
                    embed = discord.Embed(
                        title="🔗 **Useful Links**",
                        description="Our Discord server: https://discord.gg/AWAUy36Mcj\n" \
                        "Our website: https://gamerbot.mystrikingly.com\n" \
                        "Add the bot: https://discord.com/oauth2/authorize?client_id=1419270139173404782&permissions=2252627166079169&integration_type=0&scope=bot",
                        color=discord.Color.yellow()
                    )
            
            embed.set_footer(text=f"Сторінка {page + 1}/5" if lang == "uk" else f"Page {page + 1}/5")
            return embed
        
        @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
        async def prev_button(self, interaction: discord.Interaction, button: Button):
            if self.current_page > 0:
                self.current_page -= 1
                await self.update_message(interaction)
        
        @discord.ui.button(label="0| 📌", style=discord.ButtonStyle.primary)
        async def page0button(self, interaction: discord.Interaction, button: Button):
            self.current_page = 0
            await self.update_message(interaction)
        
        @discord.ui.button(label="1 | 🎮", style=discord.ButtonStyle.primary)
        async def page1utton(self, interaction: discord.Interaction, button: Button):
            self.current_page = 1
            await self.update_message(interaction)
        
        @discord.ui.button(label="2 | ⚙️", style=discord.ButtonStyle.primary)
        async def page2button(self, interaction: discord.Interaction, button: Button):
            self.current_page = 2
            await self.update_message(interaction)
        
        @discord.ui.button(label="3 | ℹ️", style=discord.ButtonStyle.primary)
        async def page3button(self, interaction: discord.Interaction, button: Button):
            self.current_page = 3
            await self.update_message(interaction)

        @discord.ui.button(label="4| 🔗", style=discord.ButtonStyle.primary)
        async def page4_button(self, interaction: discord.Interaction, button: Button):
            self.current_page = 4
            await self.update_message(interaction)
        
        @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
        async def next_button(self, interaction: discord.Interaction, button: Button):
            if self.current_page < 4:
                self.current_page += 1
                await self.update_message(interaction)
        
        async def on_timeout(self):
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except:
                pass
    
    view = HelpView()
    embed = await view.get_page_embed(interaction, 0)
    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()
    

@bot.tree.command(name="reset", description="♻️ Reset games on this server (tops are kept)")
async def reset(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    ensure_guild(gid)
    if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild):
        await interaction.response.send_message(t(gid, "🚫 Лише адміністратор може скинути.", "🚫 Only administrators can reset."), ephemeral=True)
        return
    # reset game states but keep tops
    state[gid]["word_data"]["last_word"] = ""
    state[gid]["word_data"]["last_user"] = ""
    state[gid]["word_data"]["used_words"] = []
    state[gid]["count_data"]["last_number"] = 0
    state[gid]["count_data"]["last_user"] = ""
    safe_save_state(state)
    await interaction.response.send_message(t(gid, "♻️ Ігри скинуто (топи збережені).", "♻️ Games reset (tops preserved)."), ephemeral=True)

@bot.tree.command(name="top", description="🏆 Show top players on this server")
async def top_cmd(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    ensure_guild(gid)
    wd_top = state[gid]["word_data"].get("top", {})
    cd_top = state[gid]["count_data"].get("top", {})
    rps_top = state[gid]["rps_data"].get("top", {})
    lang = get_language(gid)

    def fmt(top_dict):
        if not top_dict:
            return t(gid, "— немає даних —", "— no data —")
        sorted_top = sorted(top_dict.items(), key=lambda x: x[1], reverse=True)
        return "\n".join([f"{i+1}. <@{uid}> — **{score}**" for i, (uid, score) in enumerate(sorted_top[:10])])

    embed = discord.Embed(
        title=t(gid, f"🏆 ТОП гравців сервера {interaction.guild.name}", f"🏆 Top players of {interaction.guild.name}"),
        color=discord.Color.gold()
    )
    embed.add_field(name=t(gid, "🎯 Слова", "🎯 Words"), value=fmt(wd_top), inline=False)
    embed.add_field(name=t(gid, "🔢 Лічильник", "🔢 Counter"), value=fmt(cd_top), inline=False)
    embed.add_field(name=t(gid, "🎮 Камінь-Ножиці-Папір", "🎮 Rock-Paper-Scissors"), value=fmt(rps_top), inline=False)
    
    
    class TopView(View):
        def __init__(self):
            super().__init__(timeout=60)
            button_label = "🌍 Глобальний ТОП" if lang == "uk" else "🌍 Global TOP"
            self.add_item(Button(label=button_label, style=discord.ButtonStyle.primary, custom_id="global_top"))
    
    await interaction.response.send_message(embed=embed, view=TopView())

@bot.tree.command(name="servers", description="📊 Show how many servers the bot is in")
async def servers_cmd(interaction: discord.Interaction):
    total = len(bot.guilds)
    await interaction.response.send_message(f"📊 {total}", ephemeral=True)

# ---------------- Message handling (games) ----------------
@bot.event
async def on_message(message: discord.Message):
    # ignore DMs and bots
    if message.author.bot or not message.guild:
        return
     # === AI ОБРОБКА (найвищий пріоритет) ===
    if is_ai_channel(message.channel.id):
        async with message.channel.typing():
            reply = await generate_ai_response(message.author.id, message.content)
        await message.reply(reply)
        return  # Виходимо, щоб не обробляти AI повідомлення іншими іграми
    
    gid = str(message.guild.id)
    ensure_guild(gid)

    # allow slash/regular commands to process
    await bot.process_commands(message)

    # get server language and dictionaries
    lang = state[gid].get("language", "uk")
    words_set = UKRAINIAN_WORDS if lang == "uk" else ENGLISH_WORDS

    # ---- WORD GAME ----
    if state[gid].get("word_channel") == message.channel.id:
        wd = state[gid]["word_data"]
        word_raw = message.content.strip()
        word = word_raw.lower()
        user_id = str(message.author.id)

        # prevent same user twice
        if wd.get("last_user") == user_id:
            await message.reply(t(gid,
                                  "⛔ Ти не можеш писати два слова підряд. Почекай ходу іншого гравця.",
                                  "⛔ You can't post two words in a row. Wait for another player."), mention_author=False)
            return

        # basic validation: contains at least one letter
        if not word or not any(ch.isalpha() for ch in word):
            await message.reply(t(gid, "❌ Введіть правильне слово (потрібні літери).", "❌ Please enter a valid word (letters required)."), mention_author=False)
            return

        # dictionary check if words_set available
        if words_set and word not in words_set:
            await message.reply(t(gid, f"❌ {message.author.mention}, слова **{word}** немає у словнику.", f"❌ {message.author.mention}, the word **{word}** is not in the dictionary."), mention_author=False)
            return

        # check repeats (used_words)
        used = wd.setdefault("used_words", [])
        if word in used:
            await message.reply(t(gid, f"⚠️ {message.author.mention}, слово **{word}** вже використовувалося (почекай оновлення).", f"⚠️ {message.author.mention}, the word **{word}** was already used (wait for reset)."), mention_author=False)
            return

        # clear used_words every 40 entries (keep behavior requested)
        if len(used) >= 40:
            used.clear()
            await message.channel.send(t(gid, "🔄 Історія слів очищена — можна знову використовувати старі слова.", "🔄 Word history cleared — you can reuse old words now."))

        # check first letter vs last meaningful letter
        last_word = wd.get("last_word", "")
        if last_word:
            expected = get_last_meaningful_letter(last_word)
            if expected:
                if word[0] != expected:
                    # lost — ping player
                    await message.channel.send(t(gid,
                                                 f"❌ {message.author.mention} — ти програв(ла)! Очікувалась літера **{expected.upper()}**. Гра починається заново.",
                                                 f"❌ {message.author.mention} — you lost! Expected letter **{expected.upper()}**. Starting over."))
                    # reset round
                    wd["last_word"] = ""
                    wd["last_user"] = ""
                    used.clear()
                    safe_save_state(state)
                    return

        # accept word
        used.append(word)
        wd["last_word"] = word
        wd["last_user"] = user_id
        wd["top"][user_id] = wd["top"].get(user_id, 0) + 1
        safe_save_state(state)

        write_game_log(
            gid,
            f"[WORDS] {message.author} ({user_id}): {word}"
        )

        # compute last_letter to inform next player
        last_letter = get_last_meaningful_letter(word)
        await message.channel.send(t(gid,
                                     f"✅ {message.author.mention}, слово прийняте: **{word_raw.strip()}**. Наступне має починатися на **{last_letter.upper()}**.",
                                     f"✅ {message.author.mention}, word accepted: **{word_raw.strip()}**. Next must start with **{last_letter.upper()}**."))
        return

    # ---- COUNTING GAME ----
    if state[gid].get("count_channel") == message.channel.id:
        cd = state[gid]["count_data"]
        content = message.content.strip()
        user_id = str(message.author.id)

        # prevent same user twice
        if cd.get("last_user") == user_id:
            try:
                await message.add_reaction("⛔")
            except Exception:
                pass
            return

        try:
            num = int(content)
        except ValueError:
            return

        expected = cd.get("last_number", 0) + 1
        if num != expected:
            try:
                await message.add_reaction("❌")
            except Exception:
                pass
            await message.channel.send(t(gid, f"❌ {message.author.mention} — збив(ла) лічильник (очікувалось **{expected}**). Лічильник скинуто.", f"❌ {message.author.mention} — wrong number (expected **{expected}**). Counter reset."))
            cd["last_number"] = 0
            cd["last_user"] = ""
            safe_save_state(state)
            return
        
        write_game_log(
            gid,
            f"[COUNT-FAIL] {message.author} ({user_id}) sent {num}, expected {expected}"
        )

        # correct
        try:
            await message.add_reaction("✅")
        except Exception:
            pass
        cd["last_number"] = num
        cd["last_user"] = user_id
        cd["top"][user_id] = cd["top"].get(user_id, 0) + 1
        safe_save_state(state)
        count_message_cache[message.id] = {
            "content": message.content,
            "author_id": message.author.id,
            "channel_id": message.channel.id
        }

        return

#------------ EDITED MESSAGE HANDLING (counting game) ----------------
@bot.event
async def on_message_edit(before, after):
    if before.author.bot or not before.guild:
        return

    gid = str(before.guild.id)
    ensure_guild(gid)

    if state[gid].get("count_channel") != before.channel.id:
        return

    cached = count_message_cache.get(before.id)
    if not cached:
        return

    await before.channel.send(
        t(
            gid,
            f"⚠️ <@{before.author.id}> відредагував(ла) повідомлення в лічильнику!\n\n"
            f"📝 Було: `{cached['content']}`\n"
            f"✏️ Стало: `{after.content}`",
            f"⚠️ <@{before.author.id}> edited the counting message!\n\n"
            f"📝 Before: `{cached['content']}`\n"
            f"✏️ After: `{after.content}`"
        )
    )

#---------------- DELETED MESSAGE HANDLING (counting game) ----------------
@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.guild:
        return

    gid = str(message.guild.id)
    ensure_guild(gid)

    if state[gid].get("count_channel") != message.channel.id:
        return

    cached = count_message_cache.get(message.id)
    if not cached:
        return

    await message.channel.send(
        t(
            gid,
            f"🚨 <@{message.author.id}> видалив(ла) повідомлення в лічильнику!\n\n"
            f"🗑 Видалене повідомлення: `{cached['content']}`",
            f"🚨 <@{message.author.id}> deleted a counting message!\n\n"
            f"🗑 Deleted message was: `{cached['content']}`"
        )
    )
#---------------- add top's button ----------------

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data or interaction.data.get("custom_id") != "global_top":
        return
    
    # Відповідаємо одразу, щоб уникнути помилки
    await interaction.response.defer(ephemeral=True)
    
    gid = str(interaction.guild.id) if interaction.guild else ""
    lang = state.get(gid, {}).get("language", "uk")
    
    # Збираємо глобальний топ
    points = {}
    for guild_id, data in state.items():
        if guild_id.isdigit() and "rps_data" in data:
            for uid, p in data["rps_data"]["top"].items():
                if p > 0:
                    points[uid] = points.get(uid, 0) + p
    
    top = sorted(points.items(), key=lambda x: x[1], reverse=True)[:10]
    
    if not top:
        embed = discord.Embed(
            title="🌍 Глобальний ТОП" if lang == "uk" else "🌍 Global TOP",
            description="😔 Немає даних" if lang == "uk" else "😔 No data",
            color=discord.Color.orange()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🌍 Глобальний ТОП" if lang == "uk" else "🌍 Global TOP",
        color=discord.Color.gold()
    )
    
    text = ""
    for i, (uid, p) in enumerate(top):
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name
        except:
            name = uid[:8]
        
        if i == 0:
            medal = "🥇"
        elif i == 1:
            medal = "🥈"
        elif i == 2:
            medal = "🥉"
        else:
            medal = f"**#{i+1}**"
        
        text += f"{medal} **{name}** — `{p}` " + ("балів\n" if lang == "uk" else "points\n")
    
    embed.add_field(
        name="🏅 " + ("Топ гравців" if lang == "uk" else "Top Players"),
        value=text,
        inline=False
    )
    
    embed.set_footer(text=("Оновлено" if lang == "uk" else "Updated"))
    embed.timestamp = discord.utils.utcnow()
    
    await interaction.followup.send(embed=embed, ephemeral=True)

#------------premium dm-----------------

async def send_premium_dm(discord_id):

    try:

        user = await bot.fetch_user(int(discord_id))

        embed = discord.Embed(
            title="🌟 Premium Activated",
            description=(
                "Дякуємо за покупку Premium!\n\n"
                "Premium успішно активовано."
            ),
            color=discord.Color.gold()
        )

        await user.send(embed=embed)

    except Exception as e:
        print(f"DM ERROR: {e}")
    
# Додати ЦЮ функцію після send_premium_dm
def send_premium_dm_sync(discord_id):
    """Для виклику з API (синхронна обгортка)"""
    import asyncio
    asyncio.run_coroutine_threadsafe(send_premium_dm(discord_id), bot.loop)
    
@app.route("/activate-premium", methods=["POST"])
def activate_premium():
    auth = request.headers.get("Authorization")

    if auth != API_KEY:
        return {"error": "Unauthorized"}, 401

    data = request.json
    discord_id = data.get("discordId")

    if not discord_id:
        return {"error": "No discord ID"}, 400

    add_premium(discord_id)

    logging.info(f"Premium activated for {discord_id}")

    # Відправити DM (використовуємо синхронну обгортку)
    send_premium_dm_sync(discord_id)

    return {"success": True}


# ========== АВТОМАТИЧНА ПЕРЕВІРКА PREMIUM ==========
from premium import get_all_premium_users

# Зберігаємо ID користувачів, яким вже надіслали DM
sent_dm_users = set()

async def send_premium_dm(discord_id: str):
    """Надсилає DM користувачу про активацію Premium"""
    try:
        user = await bot.fetch_user(int(discord_id))
        embed = discord.Embed(
            title="🌟 Premium Activated!",
            description="Дякуємо за покупку Premium!\n\n"
                       "Тепер вам доступні всі преміум-функції бота.\n"
                       "Спробуйте: `/premium_test`",
            color=discord.Color.gold()
        )
        await user.send(embed=embed)
        logging.info(f"✅ Premium DM sent to {discord_id}")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to send DM to {discord_id}: {e}")
        return False

@tasks.loop(seconds=10)
async def check_new_premium_users():
    """Кожні 10 секунд перевіряє нових premium користувачів"""
    global sent_dm_users
    
    try:
        # Отримуємо всіх premium користувачів
        premium_data = get_all_premium_users()
        
        # Обробка різних форматів
        if isinstance(premium_data, list):
            current_premium_ids = set(str(uid) for uid in premium_data)
        elif isinstance(premium_data, dict):
            current_premium_ids = set(premium_data.keys())
        else:
            current_premium_ids = set()
        
        # Знаходимо нових (яким ще не надсилали DM)
        new_users = current_premium_ids - sent_dm_users
        
        for user_id in new_users:
            logging.info(f"🎉 New premium user detected: {user_id}")
            await send_premium_dm(user_id)
            sent_dm_users.add(user_id)
            
    except Exception as e:
        logging.error(f"Error checking premium users: {e}")

# Запускаємо перевірку при старті бота
@bot.event
async def on_ready():
    # ... твій існуючий код ...
    
    # Запускаємо перевірку premium
    if not check_new_premium_users.is_running():
        check_new_premium_users.start()
        logging.info("🔄 Premium checker started (every 10 seconds)")
# ---------------- Run ----------------
if __name__ == "__main__":
    if not TOKEN:
        logging.critical("❌ TOKEN not found in .env (key: TOKEN).")
        raise SystemExit("TOKEN not found in .env")
        
def run_api():
    app.run(host="0.0.0.0", port=5001)

threading.Thread(target=run_api).start()        
bot.run(TOKEN)
