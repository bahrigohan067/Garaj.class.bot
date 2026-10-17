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
    
    # Warnings table (Sicil ve detaylı kayıt)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            warn_id TEXT PRIMARY KEY,
            user_id INTEGER,
            moderator_id INTEGER,
            target_roles TEXT,
            warn_type TEXT,
            rule_code TEXT,
            reason TEXT,
            points INTEGER DEFAULT 0,
            action_taken TEXT,
            image_url TEXT,
            created_at TEXT,
            expires_at TEXT,
            is_cancelled INTEGER DEFAULT 0,
            log_message_id INTEGER DEFAULT 0
        )
    """)

    # User warning points and tiers (Kullanıcı ceza durumu ve puanları)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_warn_points (
            user_id INTEGER PRIMARY KEY,
            total_points INTEGER DEFAULT 0,
            kademe INTEGER DEFAULT 0,
            staff_warn_count INTEGER DEFAULT 0,
            last_warn_date TEXT,
            jail_until TEXT,
            timeout_10_applied INTEGER DEFAULT 0
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

# ==================== UYARI SİSTEMİ VERİTABANI FONKSİYONLARI ====================

def get_user_warn_data(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT total_points, kademe, staff_warn_count, last_warn_date, jail_until, timeout_10_applied
        FROM user_warn_points WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
            INSERT INTO user_warn_points (user_id, total_points, kademe, staff_warn_count, last_warn_date, jail_until, timeout_10_applied)
            VALUES (?, 0, 0, 0, NULL, NULL, 0)
        """, (user_id,))
        conn.commit()
        conn.close()
        return {
            "user_id": user_id,
            "total_points": 0,
            "kademe": 0,
            "staff_warn_count": 0,
            "last_warn_date": None,
            "jail_until": None,
            "timeout_10_applied": 0
        }
    conn.close()
    return {
        "user_id": user_id,
        "total_points": row[0] or 0,
        "kademe": row[1] or 0,
        "staff_warn_count": row[2] or 0,
        "last_warn_date": row[3],
        "jail_until": row[4],
        "timeout_10_applied": row[5] or 0
    }

def update_user_warn_data(user_id, total_points, kademe, staff_warn_count, last_warn_date, jail_until, timeout_10_applied):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_warn_points (user_id, total_points, kademe, staff_warn_count, last_warn_date, jail_until, timeout_10_applied)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            total_points = excluded.total_points,
            kademe = excluded.kademe,
            staff_warn_count = excluded.staff_warn_count,
            last_warn_date = excluded.last_warn_date,
            jail_until = excluded.jail_until,
            timeout_10_applied = excluded.timeout_10_applied
    """, (user_id, total_points, kademe, staff_warn_count, last_warn_date, jail_until, timeout_10_applied))
    conn.commit()
    conn.close()

def save_warning(warn_id, user_id, moderator_id, target_roles, warn_type, rule_code, reason, points, action_taken, expires_at, log_message_id=0, image_url=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now_str = datetime.datetime.now(TZ).isoformat()
    cursor.execute("""
        INSERT INTO warnings (
            warn_id, user_id, moderator_id, target_roles, warn_type, rule_code,
            reason, points, action_taken, image_url, created_at, expires_at,
            is_cancelled, log_message_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
    """, (warn_id, user_id, moderator_id, target_roles, warn_type, rule_code, reason, points, action_taken, image_url, now_str, expires_at, log_message_id))
    conn.commit()
    conn.close()

def set_warning_log_message_id(warn_id, message_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE warnings SET log_message_id = ? WHERE warn_id = ?", (message_id, warn_id))
    conn.commit()
    conn.close()

def set_warning_image(warn_id, image_url):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE warnings SET image_url = ? WHERE warn_id = ?", (image_url, warn_id))
    conn.commit()
    conn.close()

def get_warning(warn_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT warn_id, user_id, moderator_id, target_roles, warn_type, rule_code,
               reason, points, action_taken, image_url, created_at, expires_at,
               is_cancelled, log_message_id
        FROM warnings WHERE warn_id = ?
    """, (warn_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "warn_id": row[0],
        "user_id": row[1],
        "moderator_id": row[2],
        "target_roles": row[3],
        "warn_type": row[4],
        "rule_code": row[5],
        "reason": row[6],
        "points": row[7],
        "action_taken": row[8],
        "image_url": row[9],
        "created_at": row[10],
        "expires_at": row[11],
        "is_cancelled": row[12],
        "log_message_id": row[13]
    }

def cancel_warning(warn_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE warnings SET is_cancelled = 1 WHERE warn_id = ?", (warn_id,))
    conn.commit()
    conn.close()

def get_user_warnings(user_id, limit=20):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT warn_id, moderator_id, rule_code, reason, points, action_taken,
               image_url, created_at, expires_at, is_cancelled, warn_type
        FROM warnings WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        results.append({
            "warn_id": r[0],
            "moderator_id": r[1],
            "rule_code": r[2],
            "reason": r[3],
            "points": r[4],
            "action_taken": r[5],
            "image_url": r[6],
            "created_at": r[7],
            "expires_at": r[8],
            "is_cancelled": r[9],
            "warn_type": r[10]
        })
    return results

def get_total_warnings_count(user_id, include_cancelled=False):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if include_cancelled:
        cursor.execute("SELECT COUNT(*) FROM warnings WHERE user_id = ?", (user_id,))
    else:
        cursor.execute("SELECT COUNT(*) FROM warnings WHERE user_id = ? AND is_cancelled = 0", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_users_for_auto_pardon(days=30):
    """30 gün boyunca ceza almamış ve üzerinde puan/kademe bulunan kullanıcıları bulur."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.datetime.now(TZ)
    cursor.execute("""
        SELECT user_id, last_warn_date
        FROM user_warn_points
        WHERE (total_points > 0 OR kademe > 0 OR staff_warn_count > 0)
          AND last_warn_date IS NOT NULL
    """)
    rows = cursor.fetchall()
    conn.close()
    
    pardon_user_ids = []
    for uid, l_date in rows:
        try:
            last_dt = datetime.datetime.fromisoformat(l_date)
            if (now - last_dt).total_seconds() >= (days * 86400):
                pardon_user_ids.append(uid)
        except Exception:
            continue
    return pardon_user_ids

def reset_user_warnings_pardon(user_id):
    """Otomatik af: Kullanıcının puan ve kademesini sıfırlar (sicil kayıtlarına dokunmaz)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE user_warn_points
        SET total_points = 0, kademe = 0, staff_warn_count = 0, timeout_10_applied = 0
        WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    conn.close()

def get_expired_jails():
    """Karantina süresi (1 hafta) dolmuş kullanıcıları getirir."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now_str = datetime.datetime.now(TZ).isoformat()
    cursor.execute("SELECT user_id FROM user_warn_points WHERE jail_until IS NOT NULL AND jail_until <= ?", (now_str,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def clear_user_jail(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE user_warn_points SET jail_until = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
