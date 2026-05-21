"""
app_new.py — Uygulama giriş noktası
Sadece başlatma kodu burada.
İş mantığı için: simulator.py
API endpoint'leri için: routes.py
Veritabanı için: db.py
"""
import threading
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from db import init_db, get_db
from simulator import (
    AVATAR_COLORS, seed_historical_data,
    check_smart_alerts, simulation_loop,
)
import simulator as _sim
from routes import bp

# ── FLASK INIT ────────────────────────────────────────────────────────────────

app       = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
socketio  = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

app.register_blueprint(bp)


# ── WEBSOCKET ─────────────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    """İstemci bağlandığında mevcut tüm durumları gönder."""
    conn = get_db()
    rows = conn.execute("""
        SELECT p.id,p.name,p.age,p.city,p.sleep_score,p.avatar_color,cs.*
        FROM persons p LEFT JOIN current_state cs ON p.id=cs.person_id
        WHERE p.active=1 ORDER BY p.id
    """).fetchall()
    conn.close()
    for row in rows:
        emit("state_update", dict(row))


@socketio.on("disconnect")
def on_disconnect():
    pass


# ── BAŞLATMA ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import random

    print("Veritabanı hazırlanıyor...")
    init_db()

    conn = get_db()
    if conn.execute("SELECT COUNT(*) as n FROM persons").fetchone()["n"] == 0:
        sample = [
            ("Ayşe Yılmaz",   34, "İstanbul"),
            ("Mehmet Kaya",   28, "Ankara"),
            ("Zeynep Arslan", 41, "İzmir"),
            ("Can Demir",     25, "İstanbul"),
            ("Elif Şahin",    36, "Bursa"),
        ]
        print("Örnek kişiler ekleniyor ve geçmiş veri üretiliyor...")
        for nm, ag, ct in sample:
            conn.execute(
                "INSERT INTO persons (name,age,city,sleep_score,avatar_color) VALUES (?,?,?,?,?)",
                (nm, ag, ct, random.randint(5, 10), random.choice(AVATAR_COLORS))
            )
            conn.commit()
            pid = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
            seed_historical_data(conn, pid, days_back=14)
        print("Hazır.")
    else:
        for p in conn.execute("SELECT id FROM persons WHERE active=1").fetchall():
            seed_historical_data(conn, p["id"], days_back=14)
    conn.close()

    # İlk akıllı uyarı kontrolü
    conn2 = get_db()
    check_smart_alerts(conn2, socketio)
    conn2.close()

    # Simülasyon döngüsünü ayrı thread'de başlat
    t = threading.Thread(target=simulation_loop, args=(socketio,), daemon=True)
    t.start()

    print("Simülasyon başlatıldı — http://localhost:5000")
    socketio.run(app, debug=False, port=5000, allow_unsafe_werkzeug=True)