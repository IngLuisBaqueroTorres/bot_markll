# utils/mt5_connector.py
import MetaTrader5 as mt5
from dotenv import load_dotenv
import os
import logging

load_dotenv()

# Configurar logger para que coincida con el del bot
logger = logging.getLogger("mark2")

def mt5_connect():
    """Conecta a MetaTrader 5 con credenciales de .env."""
    login = int(os.getenv("LOGIN"))
    password = os.getenv("PASSWORD")
    server = os.getenv("SERVER")
    
    if not mt5.initialize(login=login, password=password, server=server):
        error = mt5.last_error()
        logger.error(f"Error de conexión MT5: {error}")
        return False
    
    logger.info("Conectado a MT5 correctamente")
    return True

def mt5_shutdown():
    """Cierra la conexión MT5."""
    mt5.shutdown()
    logger.info("Conexión MT5 cerrada")

def is_market_open(symbol):
    """Verifica si el mercado está abierto para el símbolo."""
    info = mt5.symbol_info(symbol)
    if not info:
        return False
    return info.trade_mode in [mt5.SYMBOL_TRADE_MODE_FULL, mt5.SYMBOL_TRADE_MODE_CLOSEONLY]

def get_candles(symbol, timeframe, count):
    """Obtiene velas históricas con máxima robustez."""
    try:
        if not mt5.symbol_select(symbol, True):
            logger.warning(f"Advertencia: No se pudo seleccionar {symbol}")
            return None
        
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        
        if rates is None or len(rates) == 0:
            logger.debug(f"Sin datos históricos recientes para {symbol}")
            return None
        
        candles = []
        for rate in rates:
            candle = {
                "time": rate.time,
                "open": rate.open,
                "high": rate.high,
                "low": rate.low,
                "close": rate.close,
                "volume": rate.tick_volume
            }
            candles.append(candle)
        
        return candles

    except Exception as e:
        logger.error(f"EXCEPCIÓN en get_candles({symbol}): {e}")
        return None


# === FUNCIÓN CLAVE: ENVÍO DE ÓRDENES 100% COMPATIBLE CON IC MARKETS RAW SPREAD ===
def send_order(symbol, order_type, volume, price, sl, tp, comment="Mark2_AI"):
    if not mt5.symbol_select(symbol, True):
        logger.error(f"No se pudo seleccionar símbolo: {symbol}")
        return None

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logger.error(f"No se encontró información del símbolo {symbol}")
        return None

    # IC Markets Raw Spread: solo acepta IOC o FOK → probamos ambos
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,                    # Slippage máximo permitido
        "magic": 234567,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,   # Primero intentamos IOC (el más usado)
    }

    # Intentar con IOC
    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f"ORDEN ABIERTA OK → {symbol} | {'BUY' if order_type == mt5.ORDER_TYPE_BUY else 'SELL'} | "
                    f"Vol: {volume:.2f} | Precio: {price:.5f} | Ticket: {result.order}")
        return result.order

    # Si falla IOC, intentamos con FOK (algunos símbolos lo requieren)
    logger.warning(f"IOC falló ({result.retcode}), reintentando con FOK en {symbol}")
    request["type_filling"] = mt5.ORDER_FILLING_FOK
    result = mt5.order_send(request)

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f"ORDEN ABIERTA OK (con FOK) → {symbol} | Ticket: {result.order}")
        return result.order

    # Si ambos fallan → error definitivo
    logger.error(f"ERROR FINAL enviando orden {symbol}: {result.retcode} - {result.comment}")
    return None


def close_position(ticket):
    """Cierra una posición por ticket."""
    positions = mt5.positions_get(ticket=ticket)
    if not positions or len(positions) == 0:
        logger.warning(f"Posición #{ticket} no encontrada")
        return False
    
    pos = positions[0]
    symbol = pos.symbol
    volume = pos.volume
    price = mt5.symbol_info_tick(symbol)
    
    if not price:
        logger.error(f"No se pudo obtener precio actual para cerrar {symbol}")
        return False

    close_price = price.bid if pos.type == mt5.ORDER_TYPE_BUY else price.ask
    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": close_type,
        "position": ticket,
        "price": close_price,
        "deviation": 20,
        "magic": 234567,
        "comment": "Cierre Mark2",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f"Posición cerrada #{ticket} | Profit: ${pos.profit:.2f}")
        return True
    else:
        logger.error(f"Error cerrando #{ticket}: {result.retcode} - {result.comment}")
        return False


def get_positions(symbol=None):
    """Obtiene posiciones abiertas."""
    try:
        if symbol:
            return mt5.positions_get(symbol=symbol)
        return mt5.positions_get()
    except Exception as e:
        logger.error(f"Error obteniendo posiciones: {e}")
        return []