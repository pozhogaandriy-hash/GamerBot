import os
import json
import psycopg2
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS premium (
            discord_id TEXT PRIMARY KEY,
            premium BOOLEAN DEFAULT TRUE,
            activated_at TIMESTAMP,
            source TEXT
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

def add_premium(discord_id, source="stripe"):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO premium (discord_id, premium, activated_at, source)
        VALUES (%s, TRUE, %s, %s)
        ON CONFLICT (discord_id) DO UPDATE SET
            premium = TRUE,
            activated_at = EXCLUDED.activated_at,
            source = EXCLUDED.source
    ''', (str(discord_id), datetime.utcnow(), source))
    conn.commit()
    cur.close()
    conn.close()
    return True

def is_premium(discord_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT premium FROM premium WHERE discord_id = %s', (str(discord_id),))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result is not None and result[0]

def get_all_premium_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT discord_id FROM premium WHERE premium = TRUE')
    users = {row[0]: {"premium": True} for row in cur.fetchall()}
    cur.close()
    conn.close()
    return users

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS premium (
            discord_id TEXT PRIMARY KEY,
            premium BOOLEAN DEFAULT TRUE,
            activated_at TIMESTAMP,
            source TEXT
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()
