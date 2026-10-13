import sqlite3
import datetime
import pytz

DB_PATH = "bot_data.db"
TZ = pytz.timezone("Europe/Istanbul")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Stats table for staff members
    # date format: YYYY-MM-DD
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff_stats (
            user_id INTEGER,
            date TEXT,
            discord_active_seconds INTEGER DEFAULT 0,
            voice_active_seconds INTEGER DEFAULT 0,
            tickets_closed INTEGER DEFAULT 0,
            supports_finished INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date)
        )
    """)
    
    # Voice sessions for tracking duration
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS voice_sessions (
            user_id INTEGER PRIMARY KEY,
            join_time TEXT
        )
    """)
    
    # Tickets info
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            channel_id INTEGER PRIMARY KEY,
            creator_id INTEGER,
            created_at TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def get_today_str():
    return datetime.datetime.now(TZ).strftime("%Y-%m-%d")

def add_ticket_closed(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today = get_today_str()
    cursor.execute("""
        INSERT INTO staff_stats (user_id, date, tickets_closed) 
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, date) DO UPDATE SET tickets_closed = tickets_closed + 1
    """, (user_id, today))
    conn.commit()
    conn.close()

def add_support_finished(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today = get_today_str()
    cursor.execute("""
        INSERT INTO staff_stats (user_id, date, supports_finished) 
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, date) DO UPDATE SET supports_finished = supports_finished + 1
    """, (user_id, today))
    conn.commit()
    conn.close()

def add_voice_time(user_id, seconds):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today = get_today_str()
    cursor.execute("""
        INSERT INTO staff_stats (user_id, date, voice_active_seconds) 
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET voice_active_seconds = voice_active_seconds + ?
    """, (user_id, today, seconds, seconds))
    conn.commit()
    conn.close()

def add_discord_active_time(user_id, seconds):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today = get_today_str()
    cursor.execute("""
        INSERT INTO staff_stats (user_id, date, discord_active_seconds) 
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET discord_active_seconds = discord_active_seconds + ?
    """, (user_id, today, seconds, seconds))
    conn.commit()
    conn.close()

def get_stats_for_date(date):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, discord_active_seconds, voice_active_seconds, tickets_closed, supports_finished FROM staff_stats WHERE date = ?", (date,))
    rows = cursor.fetchall()
    conn.close()
    return rows
