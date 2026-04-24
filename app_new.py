"""
app.py — Uygulama giriş noktası
Flask uygulamasını başlatır, modülleri bir araya getirir.

Proje yapısı:
  app.py           → Başlatma
  db.py            → Veritabanı katmanı (tablo tanımları, ham sorgu fonksiyonları)
  simulator.py     → Simülasyon motoru (dağılım modelleri, biyometrik hesaplamalar, döngü)
  routes.py        → HTTP API endpoint'ları
  analysis_routes.py → Analiz endpoint'ları
  config.py        → API anahtarları ve ayarlar

Kurulum:
  pip install flask flask-cors flask-socketio
  python app.py
"""
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
import threading, random

from db import init_db, get_db, DB_PATH
from simulator import (AVATAR_COLORS, seed_historical_data,
                        check_smart_alerts, simulation_loop)
from routes import register_routes

# ── Uygulama başlatma ──────────────────────────────────────────────────────────
app      = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Route'ları kaydet
register_routes(app, socketio)

# ── Veritabanı & başlangıç verisi ─────────────────────────────────────────────
if __name__ == "__main__":
    print("Veritabanı hazırlanıyor...")
    init_db()

    conn = get_db()
    if conn.execute("SELECT COUNT(*) as n FROM persons").fetchone()["n"] == 0:
        sample = [
            ("Ayşegül Albayrak", 22, "Bursa"),
            ("Mehmet Kaya",      28, "Ankara"),
            ("Zeynep Arslan",    41, "İzmir"),
            ("Can Demir",        25, "İstanbul"),
            ("Elif Şahin",       36, "Bursa"),
        ]
        print("Örnek kişiler ekleniyor ve geçmiş veri üretiliyor...")
        for nm, ag, ct in sample:
            conn.execute("INSERT INTO persons (name,age,city,sleep_score,avatar_color) VALUES (?,?,?,?,?)",
                         (nm, ag, ct, random.randint(5,10), random.choice(AVATAR_COLORS)))
            conn.commit()
            pid = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
            seed_historical_data(conn, pid, days_back=14)
        print("Hazır.")
    else:
        persons = conn.execute("SELECT id FROM persons WHERE active=1").fetchall()
        for p in persons:
            seed_historical_data(conn, p["id"], days_back=14)

    conn.close()

    # İlk akıllı uyarı kontrolü
    conn2 = get_db()
    check_smart_alerts(conn2)
    conn2.close()

    # Simülasyon döngüsünü başlat
    t = threading.Thread(target=simulation_loop, args=(socketio,), daemon=True)
    t.start()
    print("Simülasyon başlatıldı — http://localhost:5000")
    socketio.run(app, debug=False, port=5000, allow_unsafe_werkzeug=True)