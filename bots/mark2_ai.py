# bots/mark2_ai.py → VERSIÓN ÓPTIMA Y LIMPIA (18 nov 2025)
import time
import json
import os
import csv
import logging
import threading
from datetime import datetime, timedelta

import MetaTrader5 as mt5
import requests
import pandas as pd

from utils.mt5_connector import mt5_connect, send_order, close_position, get_positions
from utils.feed_selector import get_feed
from utils.telegram_notifier import (
    notify_bot_started, notify_status, notify_trade, notify_close,
    notify_error, notify_stopped, handle_telegram_command
)
from utils.settings_manager import get_settings
from utils.telegram_notifier import BOT_COMMANDS_ENABLED
from utils.allowed_symbols import is_symbol_allowed

TIMEFRAME_MAP = {
    1: mt5.TIMEFRAME_M1, 5: mt5.TIMEFRAME_M5, 15: mt5.TIMEFRAME_M15,
    30: mt5.TIMEFRAME_M30, 60: mt5.TIMEFRAME_H1, 240: mt5.TIMEFRAME_H4, 1440: mt5.TIMEFRAME_D1
}

BASE_DIR = os.path.dirname(__file__) or "."
DATA_FILE = os.path.join(BASE_DIR, "data", "stats.json")
LOG_FILE = os.path.join(BASE_DIR, "logs", "mark2_trades.csv")
APP_LOG = os.path.join(BASE_DIR, "logs", "mark2.log")
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

logger = logging.getLogger("mark2")
logger.setLevel(logging.DEBUG)
fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
fh = logging.FileHandler(APP_LOG, encoding="utf-8")
fh.setFormatter(fmt)
fh.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(fmt)
sh.setLevel(logging.INFO)
logger.addHandler(fh)
logger.addHandler(sh)

class Mark2AIPro:
    def __init__(self):
        self.settings = get_settings("settings_mark2.json")
        self.feed = get_feed(self.settings)
        self.stats = self.load_stats()

        tf_raw = int(self.settings.get("TIMEFRAME", 60))
        self.timeframe = TIMEFRAME_MAP.get(tf_raw, mt5.TIMEFRAME_H1)

        # Respeta tu settings.json → tú decides los pares
        self.pairs = [p for p in self.settings.get("PAIRS", ["EURUSD.sml"]) if is_symbol_allowed(p)]
        if not self.pairs:
            raise ValueError("Ningún par permitido en settings_mark2.json")

        self.running = True
        self.telegram_thread = None
        self.last_close_time = {}  # Cooldown por símbolo

    def load_stats(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("No pude cargar stats.json: %s", e)
        return {"trades": [], "win_rate": 0.0, "total_profit": 0.0, "last_update": None}

    def save_stats(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.exception("Error guardando stats: %s", e)

    def calculate_lot_size(self, symbol):
        info = mt5.account_info()
        balance = getattr(info, "balance", 0) or 1000
        risk_percent = 0.01  # 1% por operación
        risk_amount = balance * risk_percent
        sl_pips = float(self.settings.get("STOP_LOSS_PIPS", 20))
        value_per_pip = 10  # aproximado para pares xxxUSD con lote 1.0
        lot = risk_amount / (sl_pips * value_per_pip)
        lot = round(max(0.01, min(lot, 2.0)), 2)
        return lot

    def log_trade(self, symbol, direction=None, ticket=None, lot_size=None,
                  entry_price=None, exit_price=None, sl=None, tp=None,
                  profit=None, reason="OPEN", duration_min=None):
        try:
            point = mt5.symbol_info(symbol).point if mt5.symbol_info(symbol) else 0.00001
        except: point = 0.00001

        profit_pips = ""
        if entry_price and exit_price and direction and point:
            diff = (exit_price - entry_price) if direction == "BUY" else (entry_price - exit_price)
            profit_pips = round(diff / point, 1)

        file_exists = os.path.isfile(LOG_FILE)
        try:
            with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["timestamp","symbol","direction","ticket","lot_size",
                                     "entry_price","exit_price","sl","tp","profit_usd","profit_pips","reason","duration_min"])
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), symbol, direction or "?",
                    ticket or "?", f"{lot_size:.2f}" if lot_size else "",
                    f"{entry_price:.5f}" if entry_price else "", f"{exit_price:.5f}" if exit_price else "",
                    f"{sl:.5f}" if sl else "", f"{tp:.5f}" if tp else "",
                    f"{profit:.2f}" if profit is not None else "", profit_pips, reason,
                    f"{duration_min:.1f}" if duration_min else ""
                ])
        except Exception: logger.exception("Error escribiendo CSV")

    def update_stats(self, symbol, profit, reason):
        trade = {"symbol": symbol, "profit": float(profit), "reason": reason, "time": datetime.now().isoformat()}
        self.stats.setdefault("trades", []).append(trade)
        self.stats["total_profit"] = round(self.stats.get("total_profit", 0) + float(profit), 2)
        wins = sum(1 for t in self.stats["trades"] if t["profit"] > 0)
        total = len(self.stats["trades"])
        self.stats["win_rate"] = round((wins / total * 100), 2) if total > 0 else 0.0
        self.stats["last_update"] = datetime.now().isoformat()
        self.save_stats()

    def get_signal(self, symbol):
        try:
            if not mt5.symbol_select(symbol, True): return None
            candles = self.feed.get_candles(symbol, self.timeframe, 100)
            if candles is None or len(candles) < 3: return None
            prev = candles.iloc[-2]
            bid, ask = self.feed.get_current_price(symbol)
            if not bid or not ask: return None
            point = mt5.symbol_info(symbol).point
            pips = float(self.settings.get("SUBIDA_PIPS", 3))  # más exigente que antes
            if bid >= prev["low"] + pips * point:
                return "SELL"
            if ask <= prev["high"] - pips * point:
                return "BUY"
            return None
        except Exception:
            logger.exception("Error generando señal %s", symbol)
            return None

    def check_telegram_commands(self):
        if not BOT_COMMANDS_ENABLED: return
        try:
            token = os.getenv('TELEGRAM_BOT_TOKEN') or self.settings.get("TELEGRAM_BOT_TOKEN")
            if not token: return
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            r = requests.get(url, timeout=5)
            if r.status_code != 200: return
            for u in r.json().get("result", []):
                if "message" not in u: continue
                text = u["message"].get("text", "").strip()
                if not text.startswith("/"): continue
                res = handle_telegram_command(text)
                if res == "stop":
                    self.running = False
                    notify_stopped()
                elif res.startswith("status"):
                    bal = mt5.account_info().balance or 0
                    notify_status(bal, self.stats.get("win_rate",0), self.stats.get("total_profit",0), len(self.stats.get("trades",[])))

                elif res == "posiciones":
                    report = self.get_open_positions_report()  # ← la función que ya te di antes
                    notify_open_positions(report)
        except Exception: pass

    def run(self):
        if not mt5_connect():
            notify_error("No se pudo conectar a MT5")
            return

        balance = mt5.account_info().balance or 0
        notify_bot_started(balance, self.settings.get("STOP_WIN_PIPS",30), self.settings.get("STOP_LOSS_PIPS",20), self.pairs)

        logger.info("MARK2 PRO ÓPTIMO INICIADO | Balance: $%.2f | Pares: %s", balance, ", ".join(self.pairs))
        logger.info("="*80)

        for s in self.pairs:
            mt5.symbol_select(s, True)

        def tg():
            while self.running:
                self.check_telegram_commands()
                time.sleep(5)
        self.telegram_thread = threading.Thread(target=tg, daemon=True)
        self.telegram_thread.start()

        try:
            while self.running:
                try:
                    positions_all = get_positions() or []
                    open_symbols = {p.symbol for p in positions_all}

                    # === CIERRE TP/SL ===
                    for pos in positions_all:
                        if pos.symbol not in self.pairs: continue
                        bid, ask = self.feed.get_current_price(pos.symbol)
                        if not bid or not ask: continue
                        price = ask if pos.type == mt5.ORDER_TYPE_BUY else bid
                        reason = None
                        if pos.tp and ((pos.type == mt5.ORDER_TYPE_BUY and price >= pos.tp) or
                                       (pos.type == mt5.ORDER_TYPE_SELL and price <= pos.tp)):
                            reason = "Take Profit"
                        elif pos.sl and ((pos.type == mt5.ORDER_TYPE_BUY and price <= pos.sl) or
                                         (pos.type == mt5.ORDER_TYPE_SELL and price >= pos.sl)):
                            reason = "Stop Loss"

                        if reason:
                            close_position(pos.ticket)
                            profit = pos.profit or 0
                            dir_ = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                            notify_close(pos.symbol, profit, reason, pos.ticket)
                            self.update_stats(pos.symbol, profit, reason)
                            self.log_trade(pos.symbol, dir_, pos.ticket, pos.volume, pos.price_open, price,
                                           pos.sl, pos.tp, profit, reason)
                            self.last_close_time[pos.symbol] = datetime.now()  # cooldown

                    # === NUEVAS ÓRDENES ===
                    if len([p for p in positions_all if p.symbol in self.pairs]) < int(self.settings.get("MAX_POSITIONS", 5)):
                        for sym in self.pairs:
                            if sym in open_symbols: continue

                            # Cooldown de 15 minutos después de cerrar una operación en este par
                            last_close = self.last_close_time.get(sym)
                            if last_close and (datetime.now() - last_close).total_seconds() < 900:
                                continue

                            signal = self.get_signal(sym)
                            if not signal: continue

                            lot = self.calculate_lot_size(sym)
                            bid, ask = self.feed.get_current_price(sym)
                            if not bid or not ask: continue
                            price = ask if signal == "BUY" else bid
                            pointelf.point = mt5.symbol_info(sym).point
                            sl_pips = float(self.settings.get("STOP_LOSS_PIPS", 20))
                            tp_pips = float(self.settings.get("STOP_WIN_PIPS", 30))
                            sl = price - sl_pips * point if signal == "BUY" else price + sl_pips * point
                            tp = price + tp_pips * point if signal == "BUY" else price - tp_pips * point

                            ticket = send_order(sym, mt5.ORDER_TYPE_BUY if signal=="BUY" else mt5.ORDER_TYPE_SELL, lot, price, sl, tp)
                            if ticket:
                                notify_trade(sym, signal, price, sl, tp, ticket, lot)
                                self.log_trade(sym, signal, ticket, lot, price, sl=sl, tp=tp, reason="OPEN")
                                logger.info("ABIERTA: %s %s lote %.2f ticket %s", sym, signal, lot, ticket)

                    time.sleep(int(self.settings.get("MAIN_LOOP_DELAY", 30)))

                except Exception as e:
                    logger.warning("Error temporal (se ignora): %s", e)
                    time.sleep(10)

        except KeyboardInterrupt:
            logger.info("BOT DETENIDO POR TI")
        finally:
            self.running = False
            logger.info("MARK2 PRO DETENIDO CORRECTAMENTE")

def run_mark2_pro():
    bot = Mark2AIPro()
    bot.run()

if __name__ == "__main__":
    run_mark2_pro()

def run():
    run_mark2_pro()