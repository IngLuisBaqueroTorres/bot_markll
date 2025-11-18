# utils/telegram_notifier.py
import os
import requests
from dotenv import load_dotenv
import MetaTrader5 as mt5

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BOT_COMMANDS_ENABLED = os.getenv("BOT_COMMANDS_ENABLED", "true").lower() == "true"

def send_telegram_message(text: str):
    """Envía mensaje a Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram no configurado")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"⚠️ Error Telegram: {e}")
        return False


def notify_bot_started(balance, stop_win, stop_loss, pairs):
    msg = f"""
<b>🤖 BOT MARK2 PRO INICIADO</b>

💰 <b>BALANCE ACTUAL:</b> ${balance:.2f}
🎯 <b>STOP WIN:</b> {stop_win} pips
🛑 <b>STOP LOSS:</b> {stop_loss} pips
📊 <b>Riesgo:</b> 1% del balance por trade
👀 <b>Pares vigilados:</b> {', '.join(pairs)}

<i>Comandos disponibles: /status /posiciones /stop</i>
"""
    send_telegram_message(msg)


def notify_status(balance, win_rate, total_profit, total_trades):
    msg = f"""
<b>📊 ESTADO DEL BOT</b>

💰 <b>Balance:</b> ${balance:.2f}
📈 <b>Win Rate:</b> {win_rate:.1f}%
💵 <b>Profit Total:</b> ${total_profit:.2f}
🔄 <b>Total Trades:</b> {total_trades}

<b>Comandos:</b>
/status → Este mensaje
/posiciones → Ver trades abiertos
/stop → Detener el bot
"""
    send_telegram_message(msg)


def notify_trade(symbol, action, price, sl, tp, ticket, lot_size):
    msg = f"""
<b>🚀 TRADE ABIERTO</b>

📊 <b>Par:</b> {symbol}
📈 <b>Acción:</b> {action}
💰 <b>Lote:</b> {lot_size:.2f}
💵 <b>Precio:</b> {price:.5f}
🛑 <b>SL:</b> {sl:.5f}
🎯 <b>TP:</b> {tp:.5f}
🎫 <b>Ticket:</b> #{ticket}

<i>Riesgo: 1% del balance</i>
"""
    send_telegram_message(msg)


def notify_close(symbol, profit, reason, ticket):
    emoji = "💰" if profit >= 0 else "📉"
    color = "🟢" if profit >= 0 else "🔴"
    msg = f"""
<b>{emoji} TRADE CERRADO</b>

📊 <b>Par:</b> {symbol}
<b>{reason}</b>
{color} <b>Profit:</b> ${profit:.2f}
🎫 <b>Ticket:</b> #{ticket}
"""
    send_telegram_message(msg)


def notify_error(msg):
    send_telegram_message(f"<b>❌ ERROR BOT</b>\n<code>{msg}</code>")


def notify_stopped():
    send_telegram_message("<b>🛑 BOT DETENIDO</b>\n<i>El bot ha sido detenido correctamente</i>")


# ==================== NUEVA FUNCIÓN: /posiciones ====================
def notify_open_positions(report_text: str):
    """Envía el reporte de posiciones abiertas (usado por /posiciones)"""
    send_telegram_message(report_text)


def handle_telegram_command(command: str):
    """Maneja todos los comandos de Telegram."""
    if not BOT_COMMANDS_ENABLED:
        return "Comandos deshabilitados"

    cmd = command.strip().lower()

    if cmd in ["/start", "/status"]:
        account = mt5.account_info()
        balance = account.balance if account else 0.0
        return f"status {balance:.2f}"

    elif cmd == "/stop":
        return "stop"

    elif cmd == "/posiciones":        # ← NUEVO COMANDO
        return "posiciones"

    else:
        return ("<b>Comandos disponibles:</b>\n"
                "/status → Balance y estadísticas\n"
                "/posiciones → Ver trades abiertos ahora mismo\n"
                "/stop → Detener el bot")