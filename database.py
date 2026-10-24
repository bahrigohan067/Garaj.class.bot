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

    # Gaca-Coin user balances and progress
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_coins (
            user_id INTEGER PRIMARY KEY,
            coins INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0,
            msg_progress INTEGER DEFAULT 0,
            voice_minutes INTEGER DEFAULT 0,
            total_messages INTEGER DEFAULT 0,
            total_voice_minutes INTEGER DEFAULT 0
        )
    """)

    # Market items & stock (tier: '1m', '3m', 'perm')
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_items (
            tier TEXT,
            item_index INTEGER,
            role_id INTEGER,
            price INTEGER,
            stock INTEGER DEFAULT 0,
            PRIMARY KEY (tier, role_id)
        )
    """)

    # User active & historical role purchases
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role_id INTEGER,
            tier TEXT,
            price INTEGER,
            purchased_at TEXT,
            expires_at TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Persistent market panel message IDs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_panels (
            panel_type TEXT PRIMARY KEY,
            channel_id INTEGER,
            message_id INTEGER
        )
    """)

    # YouTube channel configuration
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS youtube_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            channel_id TEXT,
            channel_name TEXT,
            updated_at TEXT
        )
    """)

    # YouTube notified videos (prevents duplicate DM notifications)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS youtube_notified_videos (
            video_id TEXT PRIMARY KEY,
            title TEXT,
            published_at TEXT,
            notified_at TEXT
        )
    """)

    # Seed default market items with stock = 0 if not already present
    default_market = {
        "1m": [
            (1, 1561301908596072528, 40),
            (2, 1561302629454315661, 40),
            (3, 1561302447904002239, 60),
            (4, 1540461675793092668, 25),
            (5, 1561302111990452284, 20),
            (6, 1561302187290656798, 40),
            (7, 1561302317301633135, 30),
            (8, 1561302551104851978, 20),
            (9, 1561302716624670780, 40),
            (10, 1561303044585685012, 40),
            (11, 1561303095798136852, 30),
            (12, 1561303177129754725, 50),
            (13, 1561304271587115019, 25),
            (14, 1561304162933801001, 25),
            (15, 1561304468446773258, 25),
        ],
        "3m": [
            (1, 1561301908596072528, 70),
            (2, 1561302629454315661, 70),
            (3, 1561302447904002239, 110),
            (4, 1540461675793092668, 50),
            (5, 1561302111990452284, 35),
            (6, 1561302187290656798, 70),
            (7, 1561302317301633135, 55),
            (8, 1561302551104851978, 35),
            (9, 1561302716624670780, 70),
            (10, 1561303044585685012, 70),
            (11, 1561303095798136852, 30),
            (12, 1561303177129754725, 50),
        ],
        "perm": [
            (1, 1561301908596072528, 300),
            (2, 1561302629454315661, 300),
            (3, 1561302447904002239, 330),
            (4, 1540461675793092668, 150),
            (5, 1561302111990452284, 110),
            (6, 1561302187290656798, 160),
            (7, 1561302317301633135, 150),
            (8, 1561302551104851978, 80),
            (9, 1561302716624670780, 180),
            (10, 1561303044585685012, 180),
            (11, 1561303095798136852, 90),
            (12, 1561303177129754725, 150),
        ]
    }
    for tier, items in default_market.items():
        for idx, r_id, price in items:
            cursor.execute("""
                INSERT INTO market_items (tier, item_index, role_id, price, stock)
                VALUES (?, ?, ?, ?, 0)
                ON CONFLICT(tier, role_id) DO UPDATE SET
                    item_index = excluded.item_index,
                    price = excluded.price
            """, (tier, idx, r_id, price))
    
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

# ==================== GACA-COIN & ROL MARKETİ VERİTABANI FONKSİYONLARI ====================

def get_user_coin_data(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT coins, total_earned, total_spent, msg_progress, voice_minutes, total_messages, total_voice_minutes
        FROM user_coins WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
            INSERT INTO user_coins (user_id, coins, total_earned, total_spent, msg_progress, voice_minutes, total_messages, total_voice_minutes)
            VALUES (?, 0, 0, 0, 0, 0, 0, 0)
        """, (user_id,))
        conn.commit()
        conn.close()
        return {
            "user_id": user_id,
            "coins": 0,
            "total_earned": 0,
            "total_spent": 0,
            "msg_progress": 0,
            "voice_minutes": 0,
            "total_messages": 0,
            "total_voice_minutes": 0
        }
    conn.close()
    return {
        "user_id": user_id,
        "coins": row[0] or 0,
        "total_earned": row[1] or 0,
        "total_spent": row[2] or 0,
        "msg_progress": row[3] or 0,
        "voice_minutes": row[4] or 0,
        "total_messages": row[5] or 0,
        "total_voice_minutes": row[6] or 0
    }

def increment_user_message_coin(user_id):
    """Her 20 mesajda +1 Gaca-Coin verir. Dönen değer: (kazandi_mi, yeni_bakiye, toplam_mesaj, ilerleme)"""
    data = get_user_coin_data(user_id)
    new_progress = data["msg_progress"] + 1
    new_total_msgs = data["total_messages"] + 1
    coins = data["coins"]
    total_earned = data["total_earned"]
    earned = False

    if new_progress >= 20:
        new_progress = 0
        coins += 1
        total_earned += 1
        earned = True

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE user_coins
        SET coins = ?, total_earned = ?, msg_progress = ?, total_messages = ?
        WHERE user_id = ?
    """, (coins, total_earned, new_progress, new_total_msgs, user_id))
    conn.commit()
    conn.close()
    return earned, coins, new_total_msgs, new_progress

def increment_user_voice_minute_coin(user_id, minutes=1):
    """Her 5 dakika seste durmada +1 Gaca-Coin verir. Dönen değer: (kazanilan_coin, yeni_bakiye, toplam_dakika, ilerleme)"""
    data = get_user_coin_data(user_id)
    new_voice_prog = data["voice_minutes"] + minutes
    new_total_voice = data["total_voice_minutes"] + minutes
    coins = data["coins"]
    total_earned = data["total_earned"]
    earned_coins = 0

    if new_voice_prog >= 5:
        earned_coins = new_voice_prog // 5
        new_voice_prog = new_voice_prog % 5
        coins += earned_coins
        total_earned += earned_coins

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE user_coins
        SET coins = ?, total_earned = ?, voice_minutes = ?, total_voice_minutes = ?
        WHERE user_id = ?
    """, (coins, total_earned, new_voice_prog, new_total_voice, user_id))
    conn.commit()
    conn.close()
    return earned_coins, coins, new_total_voice, new_voice_prog

def adjust_user_coins(user_id, amount):
    """Founder/Yönetici tarafından kullanıcıya coin ekleme veya çıkarma."""
    data = get_user_coin_data(user_id)
    new_coins = max(0, data["coins"] + amount)
    new_earned = data["total_earned"] + amount if amount > 0 else data["total_earned"]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE user_coins SET coins = ?, total_earned = ? WHERE user_id = ?", (new_coins, new_earned, user_id))
    conn.commit()
    conn.close()
    return new_coins

def get_market_items(tier=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if tier:
        cursor.execute("""
            SELECT tier, item_index, role_id, price, stock
            FROM market_items WHERE tier = ? ORDER BY item_index ASC
        """, (tier,))
    else:
        cursor.execute("""
            SELECT tier, item_index, role_id, price, stock
            FROM market_items ORDER BY tier ASC, item_index ASC
        """)
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "tier": r[0],
            "item_index": r[1],
            "role_id": r[2],
            "price": r[3],
            "stock": r[4]
        }
        for r in rows
    ]

def get_market_item(tier, role_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tier, item_index, role_id, price, stock
        FROM market_items WHERE tier = ? AND role_id = ?
    """, (tier, role_id))
    r = cursor.fetchone()
    conn.close()
    if not r:
        return None
    return {
        "tier": r[0],
        "item_index": r[1],
        "role_id": r[2],
        "price": r[3],
        "stock": r[4]
    }

def update_market_stock(tier, role_id, amount, mode="add"):
    """Market stoğunu günceller. mode='add' ise üstüne ekler, mode='set' ise doğrudan eşitler."""
    item = get_market_item(tier, role_id)
    if not item:
        return None
    if mode == "set":
        new_stock = max(0, amount)
    else:
        new_stock = max(0, item["stock"] + amount)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE market_items SET stock = ? WHERE tier = ? AND role_id = ?", (new_stock, tier, role_id))
    conn.commit()
    conn.close()
    return new_stock

def get_user_active_purchases(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, role_id, tier, price, purchased_at, expires_at, is_active
        FROM user_purchases WHERE user_id = ? AND is_active = 1
        ORDER BY purchased_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "user_id": r[1],
            "role_id": r[2],
            "tier": r[3],
            "price": r[4],
            "purchased_at": r[5],
            "expires_at": r[6],
            "is_active": r[7]
        }
        for r in rows
    ]

def has_active_role_purchase(user_id, role_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM user_purchases
        WHERE user_id = ? AND role_id = ? AND is_active = 1
    """, (user_id, role_id))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def create_role_purchase(user_id, role_id, tier, price, expires_at):
    """Coin düşer, stok düşer ve satın alma kaydı oluşturur."""
    now_str = datetime.datetime.now(TZ).isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT coins, total_spent FROM user_coins WHERE user_id = ?", (user_id,))
    u_row = cursor.fetchone()
    current_coins = u_row[0] if u_row else 0
    current_spent = u_row[1] if u_row else 0

    cursor.execute("SELECT stock FROM market_items WHERE tier = ? AND role_id = ?", (tier, role_id))
    m_row = cursor.fetchone()
    current_stock = m_row[0] if m_row else 0

    if current_stock <= 0:
        conn.close()
        return False, "stok_yok", current_coins, 0

    if current_coins < price:
        conn.close()
        return False, "bakiye_yetersiz", current_coins, current_stock

    new_coins = current_coins - price
    new_spent = current_spent + price
    new_stock = current_stock - 1

    cursor.execute("UPDATE user_coins SET coins = ?, total_spent = ? WHERE user_id = ?", (new_coins, new_spent, user_id))
    cursor.execute("UPDATE market_items SET stock = ? WHERE tier = ? AND role_id = ?", (new_stock, tier, role_id))
    cursor.execute("""
        INSERT INTO user_purchases (user_id, role_id, tier, price, purchased_at, expires_at, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, (user_id, role_id, tier, price, now_str, expires_at))

    conn.commit()
    conn.close()
    return True, "basarili", new_coins, new_stock

def get_expired_role_purchases():
    """Süresi dolmuş aktif rol satın alımlarını döndürür."""
    now_str = datetime.datetime.now(TZ).isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, role_id, tier, price, purchased_at, expires_at
        FROM user_purchases
        WHERE is_active = 1 AND expires_at IS NOT NULL AND expires_at <= ?
    """, (now_str,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "user_id": r[1],
            "role_id": r[2],
            "tier": r[3],
            "price": r[4],
            "purchased_at": r[5],
            "expires_at": r[6]
        }
        for r in rows
    ]

def mark_purchase_expired(purchase_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE user_purchases SET is_active = 0 WHERE id = ?", (purchase_id,))
    conn.commit()
    conn.close()

def save_market_panel(panel_type, channel_id, message_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO market_panels (panel_type, channel_id, message_id)
        VALUES (?, ?, ?)
        ON CONFLICT(panel_type) DO UPDATE SET
            channel_id = excluded.channel_id,
            message_id = excluded.message_id
    """, (panel_type, channel_id, message_id))
    conn.commit()
    conn.close()

def get_market_panel(panel_type):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, message_id FROM market_panels WHERE panel_type = ?", (panel_type,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {"channel_id": row[0], "message_id": row[1]}

def get_top_coin_users(limit=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, coins, total_earned, total_spent
        FROM user_coins ORDER BY coins DESC, total_earned DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"user_id": r[0], "coins": r[1], "total_earned": r[2], "total_spent": r[3]}
        for r in rows
    ]

# ==================== YOUTUBE BİLDİRİM VERİTABANI FONKSİYONLARI ====================

def set_youtube_config(channel_id, channel_name=""):
    now_str = datetime.datetime.now(TZ).isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO youtube_config (id, channel_id, channel_name, updated_at)
        VALUES (1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            channel_id = excluded.channel_id,
            channel_name = excluded.channel_name,
            updated_at = excluded.updated_at
    """, (channel_id, channel_name, now_str))
    conn.commit()
    conn.close()

def get_youtube_config():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, channel_name, updated_at FROM youtube_config WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "channel_id": row[0],
        "channel_name": row[1] or "GararjClass",
        "updated_at": row[2]
    }

def is_youtube_video_notified(video_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM youtube_notified_videos WHERE video_id = ?", (video_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def mark_youtube_video_notified(video_id, title="", published_at=""):
    now_str = datetime.datetime.now(TZ).isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO youtube_notified_videos (video_id, title, published_at, notified_at)
        VALUES (?, ?, ?, ?)
    """, (video_id, title, published_at, now_str))
    conn.commit()
    conn.close()

def get_notified_videos_count():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM youtube_notified_videos")
    count = cursor.fetchone()[0]
    conn.close()
    return count

