"""
config.py — Uygulama yapılandırması
API anahtarları ve global ayarlar buradan yönetilir.
"""
import os

# Anthropic API Key — ortam değişkeninden al veya buraya yaz
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DB_PATH = "simulasyon_v3.db"