"""
analysis_routes.py — Analiz endpoint'ları
Örüntü analizi, günlük profil karşılaştırması ve kapsamlı analiz endpoint'ları.
"""
from flask import jsonify, request
from datetime import datetime, timedelta
import statistics as _stats

from db import get_db
from simulator import compute_health_score


def register_analysis_routes(app):
    """Analiz route'larını Flask uygulamasına kaydet."""

    @app.route("/api/pattern_analysis/<int:pid>", methods=["GET"])
    def get_pattern_analysis(pid):
        """
        Kişiye özgü günlük yaşam örüntüsü analizi.
        - Tüm metrikler için kişisel norm hesapla (ortalama + std)
        - Her gün için sapmayı tespit et
        - İleriye yönelik 3 günlük tahmin üret
        """
        days_back = int(request.args.get("days", 14))
        conn = get_db()

        person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
        if not person:
            conn.close()
            return jsonify({"error": "Kişi bulunamadı"}), 404

        # Her gün için tam profil çıkar
        daily = []
        for i in range(days_back - 1, -1, -1):
            d       = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            label   = (datetime.now() - timedelta(days=i)).strftime("%d/%m")
            weekday = (datetime.now() - timedelta(days=i)).strftime("%A")
            is_weekend = weekday in ["Saturday", "Sunday"]
            weekday_tr = {"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar",
                          "Thursday":"Per","Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(weekday, weekday)

            def safe_hour(timestr):
                if not timestr: return None
                try:
                    dt = datetime.fromisoformat(timestr)
                    return round(dt.hour + dt.minute / 60, 2)
                except:
                    try:
                        parts = timestr.split(":")
                        return round(int(parts[0]) + int(parts[1]) / 60, 2)
                    except:
                        return None

            # Uyku
            sleep_rec = conn.execute("""
                SELECT start_time, end_time, duration_mins FROM activity_log
                WHERE person_id=? AND activity_type='sleep'
                  AND date(start_time,'localtime')=?
                ORDER BY duration_mins DESC LIMIT 1
            """, (pid, d)).fetchone()
            wake_hour  = safe_hour(sleep_rec["end_time"])   if sleep_rec else None
            sleep_hour = safe_hour(sleep_rec["start_time"]) if sleep_rec else None
            sleep_mins = sleep_rec["duration_mins"] if sleep_rec else 0

            # İlk aktivite saati (uyku dışı)
            first_act = conn.execute("""
                SELECT start_time, activity_name FROM activity_log
                WHERE person_id=? AND activity_type != 'sleep'
                  AND date(start_time,'localtime')=?
                ORDER BY start_time ASC LIMIT 1
            """, (pid, d)).fetchone()
            first_act_hour = safe_hour(first_act["start_time"]) if first_act else None
            first_act_name = first_act["activity_name"] if first_act else None

            # İlk egzersiz saati ve süresi
            exercise = conn.execute("""
                SELECT start_time, SUM(duration_mins) as total_dur,
                       COUNT(*) as cnt
                FROM activity_log
                WHERE person_id=? AND activity_type='active'
                  AND date(start_time,'localtime')=?
                GROUP BY date(start_time,'localtime')
                ORDER BY start_time ASC LIMIT 1
            """, (pid, d)).fetchone()
            exercise_hour = safe_hour(exercise["start_time"]) if exercise else None
            exercise_mins = int(exercise["total_dur"] or 0) if exercise else 0

            # Yemek saatleri
            meals = conn.execute("""
                SELECT start_time FROM activity_log
                WHERE person_id=? AND activity_type='meal'
                  AND date(start_time,'localtime')=?
                ORDER BY start_time ASC
            """, (pid, d)).fetchall()
            meal_hours = [safe_hour(m["start_time"]) for m in meals if safe_hour(m["start_time"])]

            # Dışarı çıkış (aktif aktivite — yürüyüş, bisiklet, alışveriş vb.)
            outdoor = conn.execute("""
                SELECT start_time FROM activity_log
                WHERE person_id=? AND activity_type='active'
                  AND date(start_time,'localtime')=?
                ORDER BY start_time ASC LIMIT 1
            """, (pid, d)).fetchone()
            outdoor_hour = safe_hour(outdoor["start_time"]) if outdoor else None

            # Günlük metrikler
            metrics = conn.execute("""
                SELECT COALESCE(MAX(steps_snap),0) as steps,
                       COALESCE(MAX(calories_snap),0) as calories,
                       COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as active_mins,
                       COUNT(*) as event_count
                FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?
            """, (pid, d)).fetchone()

            sensor = conn.execute("""
                SELECT ROUND(AVG(heart_rate),1) as avg_hr,
                       ROUND(AVG(spo2),1) as avg_spo2,
                       ROUND(AVG(stress_level),1) as avg_stress,
                       ROUND(AVG(hrv),1) as avg_hrv,
                       MAX(heart_rate) as max_hr,
                       MIN(CASE WHEN heart_rate>0 THEN heart_rate END) as min_hr
                FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?
            """, (pid, d)).fetchone()

            daily.append({
                "date": d, "label": label, "weekday": weekday_tr, "is_weekend": is_weekend,
                "wake_hour":     wake_hour,
                "sleep_hour":    sleep_hour,
                "sleep_mins":    sleep_mins,
                "first_act_hour": first_act_hour,
                "first_act_name": first_act_name,
                "exercise_hour":  exercise_hour,
                "exercise_mins":  exercise_mins,
                "outdoor_hour":   outdoor_hour,
                "meal_hours":     meal_hours,
                "meal_count":     len(meal_hours),
                "first_meal_hour": meal_hours[0] if meal_hours else None,
                "last_meal_hour":  meal_hours[-1] if meal_hours else None,
                "steps":       int(metrics["steps"] or 0),
                "calories":    round(float(metrics["calories"] or 0), 1),
                "active_mins": int(metrics["active_mins"] or 0),
                "avg_hr":      float(sensor["avg_hr"] or 0),
                "avg_spo2":    float(sensor["avg_spo2"] or 0),
                "avg_stress":  float(sensor["avg_stress"] or 0),
                "avg_hrv":     float(sensor["avg_hrv"] or 0),
                "max_hr":      int(sensor["max_hr"] or 0),
            })

        # Aktif günler (veri olan günler)
        active = [d for d in daily if d["event_count"] > 0] if False else [d for d in daily if d["steps"] > 0 or d["avg_hr"] > 0]

        # ── Norm hesapla (hafta içi / hafta sonu ayrı) ────────────────────────────
        import statistics

        def calc_norm(vals):
            """Bir metrik için norm hesapla"""
            vals = [v for v in vals if v is not None and v > 0]
            if len(vals) < 2:
                return {"mean": vals[0] if vals else None, "std": 0, "min": vals[0] if vals else None, "max": vals[0] if vals else None, "n": len(vals)}
            mean = sum(vals) / len(vals)
            std  = statistics.stdev(vals)
            return {
                "mean": round(mean, 2),
                "std":  round(std, 2),
                "min":  round(min(vals), 2),
                "max":  round(max(vals), 2),
                "low":  round(mean - std, 2),
                "high": round(mean + std, 2),
                "n":    len(vals)
            }

        weekday_data  = [d for d in active if not d["is_weekend"]]
        weekend_data  = [d for d in active if d["is_weekend"]]

        def norms_for(data):
            return {
                "wake_hour":      calc_norm([d["wake_hour"]      for d in data]),
                "sleep_hour":     calc_norm([d["sleep_hour"]     for d in data]),
                "sleep_mins":     calc_norm([d["sleep_mins"]     for d in data]),
                "first_act_hour": calc_norm([d["first_act_hour"] for d in data]),
                "exercise_hour":  calc_norm([d["exercise_hour"]  for d in data]),
                "exercise_mins":  calc_norm([d["exercise_mins"]  for d in data]),
                "outdoor_hour":   calc_norm([d["outdoor_hour"]   for d in data]),
                "first_meal_hour":calc_norm([d["first_meal_hour"]for d in data]),
                "last_meal_hour": calc_norm([d["last_meal_hour"] for d in data]),
                "meal_count":     calc_norm([d["meal_count"]     for d in data]),
                "steps":          calc_norm([d["steps"]          for d in data]),
                "calories":       calc_norm([d["calories"]       for d in data]),
                "active_mins":    calc_norm([d["active_mins"]    for d in data]),
                "avg_hr":         calc_norm([d["avg_hr"]         for d in data]),
                "avg_spo2":       calc_norm([d["avg_spo2"]       for d in data]),
                "avg_stress":     calc_norm([d["avg_stress"]     for d in data]),
                "avg_hrv":        calc_norm([d["avg_hrv"]        for d in data]),
            }

        norms = {
            "weekday": norms_for(weekday_data) if weekday_data else {},
            "weekend": norms_for(weekend_data) if weekend_data else {},
            "all":     norms_for(active)       if active       else {},
        }

        # ── Sapma hesapla ─────────────────────────────────────────────────────────
        def deviation_score(value, norm):
            """Değerin normdan kaç std sapma uzakta olduğunu hesapla"""
            if value is None or norm is None or norm.get("mean") is None:
                return None
            if norm.get("std", 0) == 0:
                return 0
            return round((value - norm["mean"]) / norm["std"], 2)

        METRICS = [
            ("wake_hour",       "Uyanış Saati",        "saat",  False),
            ("sleep_hour",      "Uyku Saati",           "saat",  False),
            ("sleep_mins",      "Uyku Süresi",          "dk",    True),
            ("first_act_hour",  "İlk Aktivite Saati",   "saat",  False),
            ("exercise_hour",   "Egzersiz Saati",       "saat",  False),
            ("exercise_mins",   "Egzersiz Süresi",      "dk",    True),
            ("outdoor_hour",    "Dışarı Çıkış Saati",   "saat",  False),
            ("first_meal_hour", "İlk Yemek Saati",      "saat",  False),
            ("last_meal_hour",  "Son Yemek Saati",      "saat",  False),
            ("steps",           "Adım Sayısı",          "adım",  True),
            ("calories",        "Kalori",               "kcal",  True),
            ("active_mins",     "Aktif Süre",           "dk",    True),
            ("avg_hr",          "Ort. Nabız",           "bpm",   False),
            ("avg_stress",      "Ort. Stres",           "/100",  False),
            ("avg_hrv",         "Ort. HRV",             "",      True),
            ("avg_spo2",        "Ort. SpO₂",            "%",     True),
        ]

        for day in active:
            norm_key = "weekend" if day["is_weekend"] else "weekday"
            day_norms = norms.get(norm_key) or norms.get("all") or {}
            day["deviations"] = {}
            day["deviation_flags"] = []

            for key, label, unit, higher_better in METRICS:
                val  = day.get(key)
                norm = day_norms.get(key)
                dev  = deviation_score(val, norm)
                day["deviations"][key] = dev

                if dev is not None and abs(dev) >= 1.5:
                    direction = "yüksek" if dev > 0 else "düşük"
                    severity  = "kritik" if abs(dev) >= 2.5 else "uyarı"
                    # Yüksek/düşük yorumu metriğe göre farklılaştır
                    if not higher_better:
                        interpretation = f"normalden {round(abs(dev),1)} std {'geç' if dev > 0 else 'erken'}"
                        if key in ["avg_stress"]:
                            interpretation = f"normalden {round(abs(dev),1)} std {'yüksek' if dev > 0 else 'düşük'}"
                    else:
                        interpretation = f"normalden {round(abs(dev),1)} std {'fazla' if dev > 0 else 'az'}"

                    day["deviation_flags"].append({
                        "metric":         key,
                        "label":          label,
                        "value":          val,
                        "norm_mean":      norm.get("mean") if norm else None,
                        "deviation":      dev,
                        "direction":      direction,
                        "severity":       severity,
                        "interpretation": interpretation,
                        "unit":           unit,
                    })

        # ── Tahmin (gelecek 3 gün) ────────────────────────────────────────────────
        def weighted_trend(vals, weights=None):
            vals = [v for v in vals if v is not None and v > 0]
            if not vals: return None, 0
            if len(vals) < 2: return vals[-1], 0
            if weights is None:
                weights = list(range(1, len(vals) + 1))
            weights = weights[-len(vals):]
            total_w = sum(weights)
            mean = sum(v * w for v, w in zip(vals, weights)) / total_w
            # Lineer trend eğimi
            n = len(vals)
            mx = (n - 1) / 2
            my = sum(vals) / n
            num   = sum((i - mx) * (v - my) for i, v in enumerate(vals))
            denom = sum((i - mx) ** 2 for i in range(n))
            slope = num / denom if denom != 0 else 0
            return round(mean, 2), round(slope, 3)

        recent = active[-7:] if len(active) >= 7 else active
        weights = list(range(1, len(recent) + 1))

        predictions = []
        for day_ahead in range(1, 4):
            pred_date    = (datetime.now() + timedelta(days=day_ahead)).strftime("%d/%m")
            pred_weekday = (datetime.now() + timedelta(days=day_ahead)).strftime("%A")
            is_weekend   = pred_weekday in ["Saturday", "Sunday"]
            pred_wday_tr = {"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar",
                            "Thursday":"Per","Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(pred_weekday, pred_weekday)

            pred = {"date": pred_date, "weekday": pred_wday_tr, "is_weekend": is_weekend}

            for key, label, unit, higher_better in METRICS:
                vals = [d.get(key) for d in recent]
                base, slope = weighted_trend(vals, weights)
                if base is not None:
                    predicted = base + slope * day_ahead
                    # Hafta sonu düzeltmeleri
                    if is_weekend:
                        if key == "wake_hour":   predicted += 0.5
                        if key == "sleep_hour":  predicted += 0.3
                        if key == "exercise_mins": predicted *= 0.8
                        if key == "steps":       predicted *= 0.85
                        if key == "active_mins": predicted *= 0.85
                    # Sınır kontrolü
                    if key in ["avg_spo2"]:      predicted = max(90, min(100, predicted))
                    if key in ["avg_hr"]:        predicted = max(45, min(160, predicted))
                    if key in ["avg_stress"]:    predicted = max(5,  min(99,  predicted))
                    if key in ["wake_hour", "sleep_hour", "first_act_hour",
                               "exercise_hour", "outdoor_hour",
                               "first_meal_hour","last_meal_hour"]:
                        predicted = max(0, min(24, predicted))
                        h = int(predicted)
                        m = int((predicted % 1) * 60)
                        pred[key + "_str"] = f"{h:02d}:{m:02d}"
                    pred[key] = round(predicted, 2)
                else:
                    pred[key] = None

            # Norm ile karşılaştır
            norm_key  = "weekend" if is_weekend else "weekday"
            day_norms = norms.get(norm_key) or norms.get("all") or {}
            pred["expected_deviations"] = {}
            for key, label, unit, _ in METRICS:
                norm = day_norms.get(key)
                val  = pred.get(key)
                pred["expected_deviations"][key] = deviation_score(val, norm)

            # Güven seviyesi
            pred["confidence"] = "yüksek" if len(recent) >= 7 else ("orta" if len(recent) >= 4 else "düşük")
            predictions.append(pred)

        # ── Genel anomali özeti ────────────────────────────────────────────────────
        all_flags = []
        for day in active:
            for flag in day.get("deviation_flags", []):
                all_flags.append({**flag, "date": day["label"], "weekday": day["weekday"]})

        # En sık sapma gösteren metrikler
        from collections import Counter
        metric_counts = Counter(f["metric"] for f in all_flags)
        frequent_deviations = [
            {"metric": k, "label": next((m[1] for m in METRICS if m[0]==k), k),
             "count": v, "pct": round(v/max(len(active),1)*100)}
            for k, v in metric_counts.most_common(5)
        ]

        conn.close()
        return jsonify({
            "person":               dict(person),
            "daily":                active,
            "norms":                norms,
            "predictions":          predictions,
            "all_deviation_flags":  all_flags,
            "frequent_deviations":  frequent_deviations,
            "metrics_meta":         [{"key": k, "label": l, "unit": u} for k,l,u,_ in METRICS],
        })


    @app.route("/api/daily_profile/<int:pid>", methods=["GET"])
    def get_daily_profile(pid):
        """
        Kişinin günlük yaşam profili karşılaştırması ve tahmini.
        Her gün için tam profil, günler arası delta, anomali tespiti, gelecek tahmini.
        """
        days_back = int(request.args.get("days", 14))
        conn      = get_db()

        person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
        if not person:
            conn.close()
            return jsonify({"error": "Kişi bulunamadı"}), 404

        profiles = []

        for i in range(days_back - 1, -1, -1):
            d     = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            label = (datetime.now() - timedelta(days=i)).strftime("%d/%m")
            weekday = (datetime.now() - timedelta(days=i)).strftime("%A")
            weekday_tr = {"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar",
                          "Thursday":"Per","Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(weekday, weekday)

            # Uyku kaydı — uyanış ve uyku başlangıç saatleri
            sleep_rec = conn.execute("""
                SELECT start_time, end_time, duration_mins
                FROM activity_log
                WHERE person_id=? AND activity_type='sleep'
                  AND date(start_time,'localtime')=?
                ORDER BY duration_mins DESC LIMIT 1
            """, (pid, d)).fetchone()

            wake_hour   = None
            sleep_hour  = None
            sleep_mins  = 0
            if sleep_rec:
                try:
                    if sleep_rec["end_time"]:
                        end = sleep_rec["end_time"]
                        if len(end) <= 5:
                            wake_hour = int(end.split(":")[0]) + int(end.split(":")[1])/60
                        else:
                            dt = datetime.fromisoformat(end)
                            wake_hour = dt.hour + dt.minute/60
                    if sleep_rec["start_time"]:
                        st2 = sleep_rec["start_time"]
                        if len(st2) <= 5:
                            sleep_hour = int(st2.split(":")[0]) + int(st2.split(":")[1])/60
                        else:
                            dt2 = datetime.fromisoformat(st2)
                            sleep_hour = dt2.hour + dt2.minute/60
                    sleep_mins = sleep_rec["duration_mins"] or 0
                except:
                    pass

            # İlk aktivite (uyanıştan sonraki ilk non-sleep)
            first_act = conn.execute("""
                SELECT activity_name, activity_type, start_time
                FROM activity_log
                WHERE person_id=? AND activity_type != 'sleep'
                  AND date(start_time,'localtime')=?
                ORDER BY start_time ASC LIMIT 1
            """, (pid, d)).fetchone()

            first_act_hour = None
            first_act_name = None
            if first_act and first_act["start_time"]:
                try:
                    st3 = first_act["start_time"]
                    dt3 = datetime.fromisoformat(st3) if len(st3) > 5 else None
                    if dt3:
                        first_act_hour = dt3.hour + dt3.minute/60
                    first_act_name = first_act["activity_name"]
                except:
                    pass

            # Dışarı çıkış saati (ilk outdoor aktivite)
            outdoor = conn.execute("""
                SELECT start_time FROM activity_log
                WHERE person_id=? AND activity_type='active'
                  AND date(start_time,'localtime')=?
                ORDER BY start_time ASC LIMIT 1
            """, (pid, d)).fetchone()

            outdoor_hour = None
            if outdoor and outdoor["start_time"]:
                try:
                    ot = outdoor["start_time"]
                    if len(ot) > 5:
                        dt4 = datetime.fromisoformat(ot)
                        outdoor_hour = dt4.hour + dt4.minute/60
                except:
                    pass

            # Yemek saatleri
            meals = conn.execute("""
                SELECT start_time, activity_name FROM activity_log
                WHERE person_id=? AND activity_type='meal'
                  AND date(start_time,'localtime')=?
                ORDER BY start_time ASC
            """, (pid, d)).fetchall()

            meal_hours = []
            for m in meals:
                try:
                    mt = m["start_time"]
                    if mt and len(mt) > 5:
                        dt5 = datetime.fromisoformat(mt)
                        meal_hours.append(round(dt5.hour + dt5.minute/60, 2))
                except:
                    pass

            # Günlük metrikler
            metrics = conn.execute("""
                SELECT COALESCE(MAX(steps_snap),0) as steps,
                       COALESCE(MAX(calories_snap),0) as calories,
                       COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as active_mins,
                       COUNT(*) as event_count
                FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?
            """, (pid, d)).fetchone()

            sensor = conn.execute("""
                SELECT ROUND(AVG(heart_rate),1) as avg_hr,
                       ROUND(AVG(spo2),1) as avg_spo2,
                       ROUND(AVG(stress_level),1) as avg_stress,
                       ROUND(AVG(hrv),1) as avg_hrv,
                       MAX(heart_rate) as max_hr,
                       MIN(CASE WHEN heart_rate>0 THEN heart_rate END) as min_hr
                FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?
            """, (pid, d)).fetchone()

            profiles.append({
                "date":          d,
                "label":         label,
                "weekday":       weekday_tr,
                # Uyku profili
                "wake_hour":     round(wake_hour, 2)  if wake_hour  is not None else None,
                "sleep_hour":    round(sleep_hour, 2) if sleep_hour is not None else None,
                "sleep_mins":    sleep_mins,
                "wake_time_str": f"{int(wake_hour):02d}:{int((wake_hour%1)*60):02d}"   if wake_hour  is not None else "—",
                "sleep_time_str":f"{int(sleep_hour):02d}:{int((sleep_hour%1)*60):02d}" if sleep_hour is not None else "—",
                # Aktivite profili
                "first_act_hour": round(first_act_hour, 2) if first_act_hour is not None else None,
                "first_act_name": first_act_name,
                "outdoor_hour":   round(outdoor_hour, 2) if outdoor_hour is not None else None,
                "meal_hours":     meal_hours,
                "meal_count":     len(meal_hours),
                # Metrikler
                "steps":       int(metrics["steps"] or 0),
                "calories":    round(float(metrics["calories"] or 0), 1),
                "active_mins": int(metrics["active_mins"] or 0),
                "event_count": int(metrics["event_count"] or 0),
                # Sensör
                "avg_hr":     float(sensor["avg_hr"] or 0),
                "avg_spo2":   float(sensor["avg_spo2"] or 0),
                "avg_stress": float(sensor["avg_stress"] or 0),
                "avg_hrv":    float(sensor["avg_hrv"] or 0),
                "max_hr":     int(sensor["max_hr"] or 0),
                "min_hr":     int(sensor["min_hr"] or 0),
            })

        # ── Delta hesabı (günler arası fark) ──────────────────────────────────────
        active_profiles = [p for p in profiles if p["event_count"] > 0]
        for i in range(1, len(active_profiles)):
            prev = active_profiles[i-1]
            curr = active_profiles[i]

            # Uyanış saati farkı (dakika)
            if curr["wake_hour"] is not None and prev["wake_hour"] is not None:
                curr["wake_delta_mins"] = round((curr["wake_hour"] - prev["wake_hour"]) * 60)
            else:
                curr["wake_delta_mins"] = None

            # Uyku saati farkı
            if curr["sleep_hour"] is not None and prev["sleep_hour"] is not None:
                curr["sleep_delta_mins"] = round((curr["sleep_hour"] - prev["sleep_hour"]) * 60)
            else:
                curr["sleep_delta_mins"] = None

            # Adım farkı
            curr["steps_delta"] = curr["steps"] - prev["steps"]

            # Aktif süre farkı
            curr["active_delta"] = curr["active_mins"] - prev["active_mins"]

            # Stres farkı
            curr["stress_delta"] = round(curr["avg_stress"] - prev["avg_stress"], 1)

        # İlk profil için delta yok
        if active_profiles:
            for key in ["wake_delta_mins","sleep_delta_mins","steps_delta","active_delta","stress_delta"]:
                if key not in active_profiles[0]:
                    active_profiles[0][key] = None

        # ── Anomali tespiti ────────────────────────────────────────────────────────
        anomalies = []

        # Uyanış saati giderek gecikiyor mu? (son 4 gün)
        wake_hours_list = [p["wake_hour"] for p in active_profiles[-4:] if p["wake_hour"] is not None]
        if len(wake_hours_list) >= 3:
            diffs = [wake_hours_list[i+1] - wake_hours_list[i] for i in range(len(wake_hours_list)-1)]
            if all(d > 0.2 for d in diffs):
                total_drift = round((wake_hours_list[-1] - wake_hours_list[0]) * 60)
                anomalies.append({
                    "type":    "wake_drift",
                    "title":   "Uyanış Saati Giderek Gecikiyor",
                    "desc":    f"Son {len(wake_hours_list)} günde uyanış saati toplam {total_drift} dakika geriledi",
                    "severity":"warning",
                    "icon":    "🌅"
                })

        # Adım sayısı düşüş trendi
        steps_list = [p["steps"] for p in active_profiles[-5:] if p["steps"] > 0]
        if len(steps_list) >= 4:
            first_half = sum(steps_list[:len(steps_list)//2]) / (len(steps_list)//2)
            second_half = sum(steps_list[len(steps_list)//2:]) / (len(steps_list) - len(steps_list)//2)
            if second_half < first_half * 0.8:
                drop_pct = round((1 - second_half/first_half) * 100)
                anomalies.append({
                    "type":    "steps_decline",
                    "title":   "Adım Sayısı Düşüyor",
                    "desc":    f"Son dönem adım ortalaması %{drop_pct} azaldı ({int(first_half):,} → {int(second_half):,})",
                    "severity":"info",
                    "icon":    "🚶"
                })

        # Uyku düzensizliği artıyor
        sleep_list = [p["wake_hour"] for p in active_profiles if p["wake_hour"] is not None]
        if len(sleep_list) >= 5:
            spread = max(sleep_list) - min(sleep_list)
            if spread >= 2:
                anomalies.append({
                    "type":    "sleep_irregularity",
                    "title":   "Uyku Düzensizliği",
                    "desc":    f"Uyanış saatleri {round(spread*60)} dakika aralıkta değişiyor ({min(sleep_list):.1f}h - {max(sleep_list):.1f}h)",
                    "severity":"warning",
                    "icon":    "😴"
                })

        # Stres artış trendi
        stress_list = [p["avg_stress"] for p in active_profiles[-4:] if p["avg_stress"] > 0]
        if len(stress_list) >= 3:
            if all(stress_list[i] < stress_list[i+1] for i in range(len(stress_list)-1)):
                anomalies.append({
                    "type":    "stress_rising",
                    "title":   "Stres Sürekli Artıyor",
                    "desc":    f"Son {len(stress_list)} günde stres her gün arttı ({round(stress_list[0])} → {round(stress_list[-1])})",
                    "severity":"warning",
                    "icon":    "🧠"
                })

        # Aktif süre azalıyor
        active_list = [p["active_mins"] for p in active_profiles[-5:]]
        if len(active_list) >= 4 and max(active_list) > 0:
            recent_avg = sum(active_list[-3:]) / 3
            older_avg  = sum(active_list[:-3]) / max(1, len(active_list)-3)
            if older_avg > 20 and recent_avg < older_avg * 0.6:
                anomalies.append({
                    "type":    "activity_decline",
                    "title":   "Aktivite Belirgin Azaldı",
                    "desc":    f"Aktif süre ortalaması {round(older_avg)} dk'dan {round(recent_avg)} dk'ya düştü",
                    "severity":"warning",
                    "icon":    "📉"
                })

        # ── Tahmin (gelecek 3 gün) ─────────────────────────────────────────────────
        def weighted_avg(vals, weights=None):
            vals = [v for v in vals if v is not None and v > 0]
            if not vals: return None
            if weights is None or len(weights) != len(vals):
                weights = list(range(1, len(vals)+1))
            total_w = sum(weights)
            return sum(v*w for v,w in zip(vals, weights)) / total_w

        def linear_trend(vals):
            """Basit lineer trend eğimi"""
            vals = [v for v in vals if v is not None and v > 0]
            if len(vals) < 2: return 0
            n = len(vals)
            mean_x = (n-1)/2
            mean_y = sum(vals)/n
            num   = sum((i-mean_x)*(v-mean_y) for i,v in enumerate(vals))
            denom = sum((i-mean_x)**2 for i in range(n))
            return num/denom if denom != 0 else 0

        recent = active_profiles[-7:] if len(active_profiles) >= 7 else active_profiles

        wake_vals    = [p["wake_hour"]   for p in recent if p["wake_hour"] is not None]
        sleep_vals   = [p["sleep_mins"]  for p in recent if p["sleep_mins"] > 0]
        steps_vals   = [p["steps"]       for p in recent if p["steps"] > 0]
        active_vals  = [p["active_mins"] for p in recent]
        stress_vals  = [p["avg_stress"]  for p in recent if p["avg_stress"] > 0]
        hr_vals      = [p["avg_hr"]      for p in recent if p["avg_hr"] > 0]

        wake_trend   = linear_trend(wake_vals)
        steps_trend  = linear_trend(steps_vals)
        stress_trend = linear_trend(stress_vals)

        predictions = []
        for day_ahead in range(1, 4):
            pred_date  = (datetime.now() + timedelta(days=day_ahead)).strftime("%d/%m")
            pred_wday  = (datetime.now() + timedelta(days=day_ahead)).strftime("%A")
            pred_wday_tr = {"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar",
                            "Thursday":"Per","Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(pred_wday, pred_wday)
            is_weekend = pred_wday in ["Saturday","Sunday"]

            # Ağırlıklı ortalama + trend
            base_wake   = weighted_avg(wake_vals)
            base_steps  = weighted_avg(steps_vals)
            base_stress = weighted_avg(stress_vals)
            base_sleep  = weighted_avg(sleep_vals)
            base_hr     = weighted_avg(hr_vals)

            pred_wake   = round(base_wake   + wake_trend   * day_ahead, 2) if base_wake   else None
            pred_steps  = int(  base_steps  + steps_trend  * day_ahead)    if base_steps  else None
            pred_stress = round(base_stress + stress_trend * day_ahead, 1) if base_stress else None
            pred_sleep  = round(base_sleep,  1)                             if base_sleep  else None
            pred_hr     = round(base_hr, 1)                                 if base_hr     else None

            # Hafta sonu düzeltmesi
            if is_weekend and pred_wake:
                pred_wake   = round(pred_wake + 0.5, 2)
                pred_steps  = int(pred_steps  * 0.8) if pred_steps else None

            # Tahmin güven seviyesi
            conf = "yüksek" if len(recent) >= 7 else ("orta" if len(recent) >= 4 else "düşük")

            wake_str = None
            if pred_wake is not None:
                h = max(0, min(23, int(pred_wake)))
                m = int((pred_wake % 1) * 60)
                wake_str = f"{h:02d}:{m:02d}"

            predictions.append({
                "date":        pred_date,
                "weekday":     pred_wday_tr,
                "is_weekend":  is_weekend,
                "wake_time":   wake_str,
                "steps":       max(0, pred_steps)  if pred_steps  is not None else None,
                "sleep_mins":  max(0, int(pred_sleep)) if pred_sleep is not None else None,
                "avg_stress":  max(0, min(100, pred_stress)) if pred_stress is not None else None,
                "avg_hr":      pred_hr,
                "confidence":  conf,
            })

        conn.close()
        return jsonify({
            "person":   dict(person),
            "profiles": active_profiles,
            "anomalies": anomalies,
            "predictions": predictions,
        })


    # ── VERİ KATKISI: YENİ TABLOLAR ───────────────────────────────────────────────


    @app.route("/api/analysis/<int:pid>", methods=["GET"])
    def get_analysis(pid):
        days_back = int(request.args.get("days", 14))
        conn      = get_db()

        person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
        if not person:
            conn.close()
            return jsonify({"error": "Kişi bulunamadı"}), 404

        days_data = []
        for i in range(days_back - 1, -1, -1):
            d       = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            label   = (datetime.now() - timedelta(days=i)).strftime("%d/%m")
            weekday = (datetime.now() - timedelta(days=i)).strftime("%A")
            weekday_tr = {"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar",
                          "Thursday":"Per","Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(weekday, weekday)

            summary_row = conn.execute("""
                SELECT COUNT(*) as total_events,
                  SUM(CASE WHEN activity_type='active' THEN 1 ELSE 0 END) as active_count,
                  SUM(CASE WHEN activity_type='meal'   THEN 1 ELSE 0 END) as meal_count,
                  SUM(CASE WHEN activity_type='sleep'  THEN 1 ELSE 0 END) as sleep_count,
                  SUM(CASE WHEN activity_type='rest'   THEN 1 ELSE 0 END) as rest_count,
                  COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as active_mins,
                  COALESCE(SUM(CASE WHEN activity_type='sleep'  THEN duration_mins ELSE 0 END),0) as sleep_mins,
                  COALESCE(MAX(steps_snap),0)    as max_steps,
                  COALESCE(MAX(calories_snap),0) as max_cal,
                  COALESCE(AVG(heart_rate_avg),0) as avg_hr,
                  COALESCE(MAX(heart_rate_avg),0) as max_hr,
                  COALESCE(MIN(CASE WHEN heart_rate_avg>0 THEN heart_rate_avg END),0) as min_hr
                FROM activity_log
                WHERE person_id=? AND date(start_time,'localtime')=?
            """, (pid, d)).fetchone()

            sleep_rows = conn.execute("""
                SELECT start_time, end_time, duration_mins, heart_rate_avg
                FROM activity_log
                WHERE person_id=? AND activity_type='sleep'
                  AND date(start_time,'localtime')=?
                ORDER BY start_time
            """, (pid, d)).fetchall()

            sleep_records = []
            for sr in sleep_rows:
                try:
                    st_dt = datetime.fromisoformat(sr["start_time"]) if sr["start_time"] else None
                    en_dt = datetime.fromisoformat(sr["end_time"])   if sr["end_time"]   else None
                    sleep_records.append({
                        "start":         st_dt.strftime("%H:%M") if st_dt else "—",
                        "end":           en_dt.strftime("%H:%M") if en_dt else "—",
                        "duration_mins": sr["duration_mins"] or 0,
                        "hr_avg":        sr["heart_rate_avg"] or 0,
                    })
                except:
                    pass

            wake_time        = sleep_records[-1]["end"]   if sleep_records else None
            sleep_start_time = sleep_records[0]["start"]  if sleep_records else None

            sensor_row = conn.execute("""
                SELECT ROUND(AVG(heart_rate),1) as avg_hr,
                  ROUND(AVG(spo2),1)        as avg_spo2,
                  ROUND(AVG(skin_temp),2)   as avg_temp,
                  ROUND(AVG(hrv),1)         as avg_hrv,
                  ROUND(AVG(stress_level),1) as avg_stress,
                  MIN(heart_rate)           as min_hr,
                  MAX(heart_rate)           as max_hr
                FROM sensor_log
                WHERE person_id=? AND date(recorded_at,'localtime')=?
            """, (pid, d)).fetchone()

            # Isı haritası verisi: saat bazlı aktivite tipi (0-23)
            heatmap_row = []
            for h in range(24):
                row = conn.execute("""
                    SELECT activity_type, COUNT(*) as cnt
                    FROM sensor_log
                    WHERE person_id=?
                      AND date(recorded_at,'localtime')=?
                      AND strftime('%H', recorded_at) = ?
                    GROUP BY activity_type ORDER BY cnt DESC LIMIT 1
                """, (pid, d, f"{h:02d}")).fetchone()
                heatmap_row.append(row["activity_type"] if row else None)

            top_acts = conn.execute("""
                SELECT activity_name, activity_icon, activity_type, duration_mins, start_time
                FROM activity_log
                WHERE person_id=? AND date(start_time,'localtime')=?
                ORDER BY duration_mins DESC LIMIT 3
            """, (pid, d)).fetchall()

            sr  = dict(summary_row) if summary_row else {}
            snr = dict(sensor_row)  if sensor_row  else {}

            # Günlük sağlık skoru
            health_score = compute_health_score(
                sr.get("sleep_mins", 0),
                sr.get("active_mins", 0),
                snr.get("avg_stress", 50) or 50,
                snr.get("avg_hr", 75)     or 75,
                snr.get("avg_spo2", 97)   or 97,
            )

            days_data.append({
                "date":          d,
                "label":         label,
                "weekday":       weekday_tr,
                "total_events":  sr.get("total_events", 0),
                "active_count":  sr.get("active_count", 0),
                "meal_count":    sr.get("meal_count", 0),
                "sleep_count":   sr.get("sleep_count", 0),
                "rest_count":    sr.get("rest_count", 0),
                "active_mins":   sr.get("active_mins", 0),
                "sleep_mins":    sr.get("sleep_mins", 0),
                "steps":         sr.get("max_steps", 0),
                "calories":      round(sr.get("max_cal", 0), 1),
                "avg_hr":        snr.get("avg_hr")     or sr.get("avg_hr") or 0,
                "max_hr":        snr.get("max_hr")     or sr.get("max_hr") or 0,
                "min_hr":        snr.get("min_hr")     or sr.get("min_hr") or 0,
                "avg_spo2":      snr.get("avg_spo2", 0),
                "avg_temp":      snr.get("avg_temp", 0),
                "avg_hrv":       snr.get("avg_hrv", 0),
                "avg_stress":    snr.get("avg_stress", 0),
                "health_score":  health_score,
                "wake_time":         wake_time,
                "sleep_start_time":  sleep_start_time,
                "sleep_records":     sleep_records,
                "heatmap":           heatmap_row,
                "top_activities": [
                    {
                        "name":  ta["activity_name"],
                        "icon":  ta["activity_icon"],
                        "type":  ta["activity_type"],
                        "dur":   ta["duration_mins"],
                        "start": datetime.fromisoformat(ta["start_time"]).strftime("%H:%M")
                                 if ta["start_time"] else "—",
                    }
                    for ta in top_acts
                ],
            })

        # Kişi bazlı uyku düzensizlik skoru
        wake_hours = []
        for _d in days_data:
            for _r in _d["sleep_records"]:
                _end = _r.get("end","")
                if not _end or _end == "—":
                    continue
                try:
                    if len(_end) <= 5:
                        wake_hours.append(int(_end.split(":")[0]))
                    else:
                        wake_hours.append(datetime.fromisoformat(_end).hour)
                except:
                    pass
        sleep_irregularity = round(max(wake_hours) - min(wake_hours), 1) if len(wake_hours) >= 2 else 0

        # Akıllı uyarılar
        alerts = conn.execute("""
            SELECT * FROM smart_alerts WHERE person_id=?
            ORDER BY detected_at DESC LIMIT 20
        """, (pid,)).fetchall()

        conn.close()
        return jsonify({
            "person":             dict(person),
            "days":               days_data,
            "sleep_irregularity": sleep_irregularity,
            "smart_alerts":       [dict(a) for a in alerts],
        })


    # ── MAIN ─────────────────────────────────────────────────────────────────────