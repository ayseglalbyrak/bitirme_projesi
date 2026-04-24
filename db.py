"""
db.py — Veritabanı katmanı
Tüm SQLite tablo tanımları, bağlantı yönetimi ve ham veri erişim fonksiyonları.
"""
import sqlite3

DB_PATH = "simulasyon_v3.db"


def get_db():
    """Thread-safe SQLite bağlantısı döndür."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Ana uygulama tablolarını oluştur, eksik sütunları migrate et."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS persons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, age INTEGER, city TEXT,
        sleep_score INTEGER DEFAULT 7,
        avatar_color TEXT DEFAULT '#CECBF6',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        active INTEGER DEFAULT 1,
        anomaly_hr_threshold INTEGER DEFAULT 130,
        anomaly_stress_threshold INTEGER DEFAULT 75,
        health_profile TEXT DEFAULT 'balanced')""")
    c.execute("""CREATE TABLE IF NOT EXISTS current_state (
        person_id INTEGER PRIMARY KEY,
        activity_name TEXT, activity_name_en TEXT,
        activity_icon TEXT, activity_type TEXT, activity_color TEXT,
        steps INTEGER DEFAULT 0, active_mins INTEGER DEFAULT 0,
        calories REAL DEFAULT 0, screen_mins INTEGER DEFAULT 0,
        since_mins INTEGER DEFAULT 0, duration INTEGER DEFAULT 10,
        progress INTEGER DEFAULT 0, out_count INTEGER DEFAULT 0, meal_count INTEGER DEFAULT 0,
        heart_rate INTEGER DEFAULT 70, heart_rate_prev INTEGER DEFAULT 70,
        spo2 REAL DEFAULT 98.0, skin_temp REAL DEFAULT 36.5,
        hrv INTEGER DEFAULT 45, stress_level INTEGER DEFAULT 30,
        latitude REAL DEFAULT 41.015, longitude REAL DEFAULT 28.979,
        location_name TEXT DEFAULT 'ev', mood TEXT DEFAULT 'sakin',
        chart_active INTEGER DEFAULT 0, chart_rest INTEGER DEFAULT 0,
        chart_meal INTEGER DEFAULT 0, chart_sleep INTEGER DEFAULT 8,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (person_id) REFERENCES persons(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS sensor_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER,
        heart_rate INTEGER, spo2 REAL, skin_temp REAL, hrv INTEGER,
        stress_level INTEGER, steps INTEGER, calories REAL,
        activity_name TEXT, activity_type TEXT,
        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (person_id) REFERENCES persons(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER,
        activity_name TEXT, activity_name_en TEXT,
        activity_icon TEXT, activity_type TEXT,
        start_time TEXT, end_time TEXT, duration_mins INTEGER DEFAULT 0,
        steps_snap INTEGER DEFAULT 0, calories_snap REAL DEFAULT 0,
        heart_rate_avg INTEGER DEFAULT 0,
        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (person_id) REFERENCES persons(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS anomalies (
        id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER,
        message_tr TEXT, message_en TEXT,
        metric TEXT, value REAL, severity TEXT DEFAULT 'info',
        detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (person_id) REFERENCES persons(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS weather_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        condition TEXT, condition_en TEXT, icon TEXT, temp REAL,
        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS smart_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER,
        alert_type TEXT, message_tr TEXT, message_en TEXT,
        severity TEXT DEFAULT 'info',
        detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (person_id) REFERENCES persons(id))""")
    # Migration: eski DB'lere eksik sütunları ekle
    for tbl, col in [
        ("activity_log", "start_time TEXT"),
        ("activity_log", "end_time TEXT"),
        ("activity_log", "duration_mins INTEGER DEFAULT 0"),
        ("activity_log", "heart_rate_avg INTEGER DEFAULT 0"),
        ("persons", "anomaly_hr_threshold INTEGER DEFAULT 130"),
        ("persons", "anomaly_stress_threshold INTEGER DEFAULT 75"),
        ("persons", "health_profile TEXT DEFAULT 'balanced'"),
    ]:
        try:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col}")
        except Exception:
            pass
    conn.commit()
    conn.close()
    # Katkı tabloları
    conn2 = sqlite3.connect(DB_PATH)
    init_contribution_tables(conn2)
    conn2.close()


def init_contribution_tables(conn):
    """Veri katkısı tablolarını oluştur (izleme profili, özel aktivite, katkı logu)."""
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS monitoring_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        profile_type TEXT DEFAULT 'insan',
        environment TEXT DEFAULT 'genel',
        description TEXT,
        location TEXT,
        icon TEXT DEFAULT '📍',
        color TEXT DEFAULT '#534AB7',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        active INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS custom_activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        environment TEXT DEFAULT 'genel',
        hour_start INTEGER DEFAULT 8,
        hour_end INTEGER DEFAULT 18,
        duration_min INTEGER DEFAULT 10,
        duration_max INTEGER DEFAULT 60,
        frequency_per_day INTEGER DEFAULT 1,
        hr_base INTEGER DEFAULT 75,
        hr_noise INTEGER DEFAULT 8,
        spo2_base REAL DEFAULT 98.0,
        stress_base INTEGER DEFAULT 30,
        icon TEXT DEFAULT '🔵',
        color TEXT DEFAULT '#534AB7',
        distribution TEXT DEFAULT 'normal',
        dist_params TEXT DEFAULT '{}',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        active INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS environments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT DEFAULT 'genel',
        description TEXT,
        location TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        active INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS contribution_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER,
        person_id INTEGER,
        custom_activity_id INTEGER,
        environment_id INTEGER,
        profile_name TEXT,
        profile_type TEXT,
        activity_name TEXT,
        environment_name TEXT,
        environment_type TEXT,
        start_time TEXT,
        end_time TEXT,
        duration_mins INTEGER,
        heart_rate INTEGER,
        spo2 REAL,
        stress_level INTEGER,
        hour_of_day INTEGER,
        day_of_week INTEGER,
        is_weekend INTEGER DEFAULT 0,
        distribution_used TEXT DEFAULT 'normal',
        metadata TEXT,
        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    # Migration: distribution sütunları
    for tbl, col in [
        ("custom_activities", "distribution TEXT DEFAULT 'normal'"),
        ("custom_activities", "dist_params TEXT DEFAULT '{}'"),
        ("contribution_log",  "distribution_used TEXT DEFAULT 'normal'"),
    ]:
        try:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col}")
        except Exception:
            pass
    conn.commit()


# ── Ham veri erişim fonksiyonları ──────────────────────────────────────────────

def db_get_persons(active_only=True):
    conn = get_db()
    q = "SELECT * FROM persons"
    if active_only:
        q += " WHERE active=1"
    q += " ORDER BY id"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_get_current_states():
    conn = get_db()
    rows = conn.execute("""SELECT p.id,p.name,p.age,p.city,p.sleep_score,p.avatar_color,cs.*
        FROM persons p LEFT JOIN current_state cs ON p.id=cs.person_id
        WHERE p.active=1 ORDER BY p.id""").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_get_anomalies(limit=50):
    conn = get_db()
    rows = conn.execute("""SELECT a.*,p.name as person_name FROM anomalies a
        JOIN persons p ON a.person_id=p.id
        ORDER BY a.detected_at DESC LIMIT ?""", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_get_smart_alerts(limit=100):
    conn = get_db()
    rows = conn.execute("""SELECT sa.*,p.name as person_name FROM smart_alerts sa
        JOIN persons p ON sa.person_id=p.id
        ORDER BY sa.detected_at DESC LIMIT ?""", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_get_sensor_history(pid, limit=60):
    conn = get_db()
    rows = conn.execute("""SELECT * FROM sensor_log WHERE person_id=?
        ORDER BY recorded_at DESC LIMIT ?""", (pid, limit)).fetchall()
    conn.close()
    return list(reversed([dict(r) for r in rows]))


def db_get_activity_history(pid, limit=30):
    conn = get_db()
    rows = conn.execute("""SELECT * FROM activity_log WHERE person_id=?
        ORDER BY recorded_at DESC LIMIT ?""", (pid, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_get_locations():
    conn = get_db()
    rows = conn.execute("""SELECT p.id,p.name,p.avatar_color,cs.latitude,cs.longitude,
        cs.location_name,cs.activity_name,cs.activity_icon,cs.activity_type
        FROM persons p JOIN current_state cs ON p.id=cs.person_id WHERE p.active=1""").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_get_compare():
    conn = get_db()
    rows = conn.execute("""SELECT p.name,p.age,p.city,p.sleep_score,p.avatar_color,
        cs.steps,cs.active_mins,cs.calories,cs.screen_mins,cs.out_count,cs.meal_count,
        cs.heart_rate,cs.spo2,cs.stress_level,cs.hrv
        FROM persons p JOIN current_state cs ON p.id=cs.person_id
        WHERE p.active=1 ORDER BY cs.steps DESC""").fetchall()
    conn.close()
    return [dict(r) for r in rows]