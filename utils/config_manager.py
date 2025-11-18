import os
import shutil
import json

from dotenv import load_dotenv

SETTINGS_FILE = "settings.json"
ENV_FILE = ".env"


def get_settings():
    """Lee la configuración desde settings.json y .env."""
    # Cargar variables de entorno
    load_dotenv(ENV_FILE)

    # Leer credenciales
    email = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")

    # Valores por defecto
    defaults = {
        "BALANCE_MODE": "PRACTICE",
        "PAIR": "EURUSD",
        "AMOUNT": 1,
        "DURATION": 1,
        "STOP_WIN": 10,
        "STOP_LOSS": 10,
        "CANDLE_DURATION": 60,
        "NUM_CANDLES": 200,
        "TRAILING_STOP_ENABLED": False,
        "USE_PERCENT_MODE": False,
        "TRAILING_STOP_WIN_PERCENT": 2.0,
        "TRAILING_STOP_LOSS_PERCENT": 1.0
    }

    settings = {}
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)

    # Asegurar que todas las claves por defecto existan
    for key, value in defaults.items():
        settings.setdefault(key, value)

    # Inyectar credenciales desde el .env
    settings["EMAIL"] = email
    settings["PASSWORD"] = password

    return settings