# utils/settings_manager.py
import os
import json
from dotenv import load_dotenv
import logging
logger = logging.getLogger("settings manager")
logger.setLevel(logging.DEBUG)
# Carpeta raíz del proyecto (sube dos niveles desde utils/)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "bot_markll", "bots"))
logger.warning("No pude cargar stats.json: %s", BASE_DIR)
def get_settings(filename="settings.json"):
    """
    Carga settings.json o el archivo que le pases.
    Uso:
        get_settings()                  → carga settings.json (compatibilidad vieja)
        get_settings("settings_mark2.json") → carga el de Mark2
        get_settings("settings_mark3.json") → carga el de Mark3
    """
    load_dotenv()  # siempre carga .env (LOGIN, PASSWORD, SERVER, tokens, etc.)

    # ==== DEFAULTS que sirven para los dos bots (puedes ampliarlos) ====
    defaults = {
        "BROKER": "mt5",
        "TIMEFRAME": 60,                    # ahora usamos número directo
        "PAIRS": ["EURUSD.sml", "GBPUSD.sml", "USDJPY.sml"],
        "MAX_POSITIONS": 3,
        "MAIN_LOOP_DELAY": 60,
        "MAGIC_NUMBER": 20251117,
        "LEARNING_ENABLED": True,
        "MIN_TRADES": 15,
        "MIN_WIN_RATE": 58.0,
        # Mark2 specifics
        "SUBIDA_PIPS": 3,
        "STOP_LOSS_PIPS": 35,
        "STOP_WIN_PIPS": 70,
        # Mark3 specifics (los ignora Mark2 y viceversa, no pasa nada)
        "RISK_PCT": 0.5,
        "EMA_FAST": 20,
        "EMA_SLOW": 50,
        "ATR_MULT_SL": 1.4,
        "ATR_MULT_TP": 2.8,
        "MIN_ADX": 18,
        # Telegram (común)
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", "")
    }

    # ==== Ruta completa al archivo de settings ====
    settings_path = os.path.join(BASE_DIR, filename)

    settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
            print(f"✓ Cargado {filename}")
        except Exception as e:
            print(f"✗ Error leyendo {filename}: {e}")
    else:
        print(f"⚠️ No existe {filename}, se usarán solo defaults + .env")

    # ==== Combinamos defaults → archivo específico → .env ====
    final = {**defaults, **settings}

    # Inyectamos siempre las variables críticas del .env (aunque estén en el json)
    final["LOGIN"] = int(os.getenv("LOGIN", 0)) or final.get("LOGIN", 0)
    final["PASSWORD"] = os.getenv("PASSWORD", "") or final.get("PASSWORD", "")
    final["SERVER"] = os.getenv("SERVER", "") or final.get("SERVER", "")
    final["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN") or final.get("TELEGRAM_BOT_TOKEN", "")

    return final


# ===================================================================
# COMPATIBILIDAD ANTIGUA: si algún bot viejo sigue llamando sin parámetro
# ===================================================================
# (solo para que no rompa nada si tienes más bots viejos)
_old_get_settings = None
try:
    from importlib import reload
    import sys
    # Esto es solo por si alguien importa este módulo dos veces
except:
    pass

def _legacy_get_settings():
    """Versión antigua que carga solo settings.json (para no romper bots viejos)"""
    return get_settings("settings.json")

# Si alguien hace "from utils.settings_manager import get_settings" y espera la vieja,
# le damos la legacy, pero todos los nuevos usaremos con parámetro.
if 'get_settings' not in globals() or globals()['get_settings'] is _legacy_get_settings:
    import builtins
    builtins.get_settings = _legacy_get_settings  # opcional, solo por si acaso