# bots/mark3_pro.py → MARK3 PRO INMORTAL + /posiciones + LOTE DINÁMICO (18 nov 2025)
import os
import time
import json
import csv
import logging
import threading
from datetime import datetime, timedelta

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
import requests

from utils.mt5_connector import mt5_connect, send_order, close_position, get_positions
from utils.feed_selector import get_feed
from utils.telegram_notifier import (
    notify_bot_started, notify_status, notify_trade, notify_close,
    notify_error, notify_stopped, handle_telegram_command, notify_open_positions
)
from utils.settings_manager import get_settings
from utils.telegram_notifier import BOT_COMMANDS_ENABLED
from utils.allowed_symbols import is_symbol_allowed

BASE_DIR = os.path.dirname(__file__) or "."
DATA_FILE = os.path.join(BASE_DIR, "data", "mark3_stats.json")
LOG_FILE = os.path.join(BASE_DIR, "logs", "mark3_trades.csv")
APP_LOG = os.path.join(BASE_DIR, "logs", "mark3.log")
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

logger = logging.getLogger("mark3")
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

TIMEFRAME_MAP = {1: mt5.TIMEFRAME_M1, 5: mt5.TIMEFRAME_M5, 15: mt5.TIMEFRAME_M15,
                 30: mt5.TIMEFRAME_M30, 60: mt5.TIMEFRAME_H1, 240: mt5.TIMEFRAME_H4, 1440: mt5.TIMEFRAME_D1}

# ---------- indicadores ----------
def ema(series, period): return series.ewm(span=period, adjust=False).mean()
def atr(df, n=14):
    high = df['high']; low = df['low']; close = df['close']
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

class Mark3Pro:
    def __init__(self):
        self.settings = get_settings("settings_mark3.json")
        tf_raw = int(self.settings.get("TIMEFRAME", 60))
        self.timeframe = TIMEFRAME_MAP.get(tf_raw, mt5.TIMEFRAME_H1)
        self.pairs = [p for p in self.settings.get("PAIRS", ["EURUSD.sml"]) if is_symbol_allowed(p)]
        self.feed = get_feed(self.settings)
        self.stats = self._load_stats()
        self.running = True
        self.telegram_thread = None
        self.last_close_time = {}  # ← Cooldown por par

        # parámetros
        self.RISK_PCT = float(self.settings.get("RISK_PCT", 1.0)) / 100.0
        self.MAX_POSITIONS = int(self.settings.get("MAX_POSITIONS", 3))
        self.EMA_FAST = int(self.settings.get("EMA_FAST", 20))
        self.EMA_SLOW = int(self.settings.get("EMA_SLOW", 50))
        self.ATR_MULT_SL = float(self.settings.get("ATR_MULT_SL", 1.2))
        self.ATR_MULT_TP = float(self.settings.get("ATR_MULT_TP", 2.5))

    def _load_stats(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {"trades": [], "total_profit": 0.0, "win_rate": 0.0}

    def _save_stats(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, indent=2, ensure_ascii=False)
        except: pass

    def _log_trade(self, **kwargs):
        row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), kwargs.get("symbol",""), kwargs.get("dir",""),
               kwargs.get("ticket",""), kwargs.get("lots",""), kwargs.get("entry",""), kwargs.get("exit",""),
               kwargs.get("sl",""), kwargs.get("tp",""), kwargs.get("profit",""), kwargs.get("pips",""),
               kwargs.get("reason",""), kwargs.get("duration","")]
        file_exists = os.path.isfile(LOG_FILE)
        try:
            with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if not file_exists:
                    w.writerow(["timestamp","symbol","direction","ticket","lots","entry","exit","sl","tp","profit","pips","reason","duration"])
                w.writerow(row)
        except: pass

    def _calc_lots(self, symbol, sl_pips):
        info = mt5.account_info()
        balance = info.balance if info else 1000
        risk = balance * self.RISK_PCT
        si = mt5.symbol_info(symbol)
        if not si: return 0.01
        point = si.point
        value_per_pip = 10 if "USD" in symbol else 9  # aproximado
        lots = risk / (sl_pips * value_per_pip)
        lots = round(max(0.01, min(lots, 2.0)), 2)
        return lots

    # =========================================
    # NUEVA FUNCIÓN: REPORTE PARA /posiciones
    # =========================================
    def get_open_positions_report(self):
        positions = get_positions() or []
        mark3_pos = [p for p in positions if p.symbol in self.pairs]
        
        if not mark3_pos:
            return "✅ <b>MARK3</b>: No hay posiciones abiertas en este momento."
        
        lines = [f"📊 <b>MARK3 - Posiciones abiertas ({len(mark3_pos)}):</b>"]
        total_profit = 0.0
        
        for p in mark3_pos:
            dir_str = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
            profit = p.profit or 0.0
            total_profit += profit
            lines.append(
                f"• {p.symbol} {dir_str} {p.volume:.2f} lote | "
                f"Entry {p.price_open:.5f} | "
                f"Profit {profit:+.2f} USD"
            )
        
        lines.append(f"\n💰 <b>Profit flotante MARK3:</b> {total_profit:+.2f} USD")
        return "\n".join(lines)

    # =========================================
    # TELEGRAM CON /posiciones
    # =========================================
    def _telegram_fix(self):
        if not BOT_COMMANDS_ENABLED: return
        try:
            token = os.getenv('TELEGRAM_BOT_TOKEN') or self.settings.get("TELEGRAM_BOT_TOKEN")
            if not token: return
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset=-1&limit=5&timeout=1"
            r = requests.get(url, timeout=6)
            if r.status_code != 200: return
            for u in r.json().get("result", []):
                if "message" not in u: continue
                text = u["message"].get("text", "").strip()
                if not text.startswith("/"): continue

                res = handle_telegram_command(text)
                if res == "stop":
                    logger.info("COMANDO /stop → DETENIENDO MARK3")
                    self.running = False
                    notify_stopped()

                elif res.startswith("status"):
                    bal = mt5.account_info().balance or 0
                    notify_status(bal, self.stats.get("win_rate",0), self.stats.get("total_profit",0), len(self.stats["trades"]))

                elif res == "posiciones":
                    report = self.get_open_positions_report()
                    notify_open_positions(report)

                # marcar como leído
                upd_id = u.get("update_id")
                if upd_id:
                    requests.get(f"https://api.telegram.org/bot{token}/getUpdates?offset={upd_id+1}", timeout=3)
        except: pass

    def analyze_and_trade(self):
        positions_all = get_positions() or []
        open_symbols = {p.symbol for p in positions_all}

        for symbol in self.pairs:
            if len([p for p in positions_all if p.symbol in self.pairs]) >= self.MAX_POSITIONS:
                break
            if symbol in open_symbols: continue

            # Cooldown 15 minutos después de cerrar
            last_close = self.last_close_time.get(symbol)
            if last_close and (datetime.now() - last_close).total_seconds() < 900:
                continue

            try:
                if not mt5.symbol_select(symbol, True): continue
                df = self.feed.get_candles(symbol, self.timeframe, 200)
                if df is None or len(df) < 50: continue
                df = df.copy()
                for c in ["open","high","low","close"]: df[c] = pd.to_numeric(df[c], errors="coerce")
                df = df.dropna()

                df['ema20'] = ema(df['close'], 20)
                df['ema50'] = ema(df['close'], 50)
                df['atr'] = atr(df, 14)

                last = df.iloc[-2]
                curr_bid, curr_ask = self.feed.get_current_price(symbol)
                if not curr_bid or not curr_ask: continue

                trend_up = last['ema20'] > last['ema50']
                atr_val = max(last['atr'], 0.0001)
                point = mt5.symbol_info(symbol).point
                sl_distance = atr_val * self.ATR_MULT_SL
                tp_distance = atr_val * self.ATR_MULT_TP
                sl_pips = sl_distance / point

                lots = self._calc_lots(symbol, sl_pips)  # ← LOTE DINÁMICO REAL

                recent_high = df['high'].iloc[-20:-1].max()
                recent_low = df['low'].iloc[-20:-1].min()

                # BREAKOUT + TENDENCIA
                if trend_up and last['close'] > recent_high and curr_ask > last['high']:
                    sl = curr_ask - sl_distance
                    tp = curr_ask + tp_distance
                    ticket = send_order(symbol, mt5.ORDER_TYPE_BUY, lots, curr_ask, sl, tp)
                    if ticket:
                        notify_trade(symbol, "BUY", curr_ask, sl, tp, ticket, lots)
                        self._log_trade(symbol=symbol, dir="BUY", ticket=ticket, lots=lots, entry=curr_ask,
                                        sl=sl, tp=tp, reason="BREAKOUT")
                        logger.info("MARK3 BUY %s lote %.2f", symbol, lots)

                elif not trend_up and last['close'] < recent_low and curr_bid < last['low']:
                    sl = curr_bid + sl_distance
                    tp = curr_bid - tp_distance
                    ticket = send_order(symbol, mt5.ORDER_TYPE_SELL, lots, curr_bid, sl, tp)
                    if ticket:
                        notify_trade(symbol, "SELL", curr_bid, sl, tp, ticket, lots)
                        self._log_trade(symbol=symbol, dir="SELL", ticket=ticket, lots=lots, entry=curr_bid,
                                        sl=sl, tp=tp, reason="BREAKOUT")
                        logger.info("MARK3 SELL %s lote %.2f", symbol, lots)

            except Exception as e:
                logger.warning("Error analizando %s: %s", symbol, e)

    def monitor_closes(self):
        positions_all = get_positions() or []
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
                notify_close(pos.symbol, profit, reason, pos.ticket)
                self.stats["trades"].append({"profit": profit})
                self.stats["total_profit"] = round(self.stats.get("total_profit",0) + profit, 2)
                wins = sum(1 for t in self.stats["trades"] if t["profit"] > 0)
                self.stats["win_rate"] = round(wins/len(self.stats["trades"])*100, 2) if self.stats["trades"] else 0
                self._save_stats()
                self._log_trade(symbol=pos.symbol, ticket=pos.ticket, profit=profit, reason=reason)
                self.last_close_time[pos.symbol] = datetime.now()  # ← Cooldown activado

    def run(self):
        if not mt5_connect():
            notify_error("No se pudo conectar a MT5")
            return

        balance = mt5.account_info().balance or 0
        notify_bot_started(balance, f"ATR x{self.ATR_MULT_TP}", f"ATR x{self.ATR_MULT_SL}", self.pairs)
        logger.info("MARK3 PRO INMORTAL INICIADO | Balance: $%.2f | Pares: %s", balance, ", ".join(self.pairs))

        def tg_thread():
            while self.running:
                self._telegram_fix()
                time.sleep(5)
        self.telegram_thread = threading.Thread(target=tg_thread, daemon=True)
        self.telegram_thread.start()

        try:
            while self.running:
                try:
                    self.monitor_closes()
                    self.analyze_and_trade()
                    time.sleep(int(self.settings.get("MAIN_LOOP_DELAY", 45)))
                except Exception as e:
                    logger.warning("Error temporal (se ignora): %s", e)
                    time.sleep(10)
        except KeyboardInterrupt:
            logger.info("MARK3 DETENIDO POR TI (Ctrl+C)")
        finally:
            self.running = False
            logger.info("MARK3 PRO DETENIDO CORRECTAMENTE")

def run_mark3_pro():
    bot = Mark3Pro()
    bot.run()

if __name__ == "__main__":
    run_mark3_pro()

def run():
    run_mark3_pro()