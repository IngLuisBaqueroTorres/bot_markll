# utils/mt5_connector.py
import MetaTrader5 as mt5
from dotenv import load_dotenv
import os

load_dotenv()

def mt5_connect():
    """Conecta a MetaTrader 5 con credenciales de .env."""
    login = int(os.getenv("LOGIN"))
    password = os.getenv("PASSWORD")
    server = os.getenv("SERVER")
    
    if not mt5.initialize(login=login, password=password, server=server):
        error = mt5.last_error()
        print(f"Error de conexión MT5: {error}")
        return False
    
    print("Conectado a MT5")
    return True

def mt5_shutdown():
    """Cierra la conexión MT5."""
    mt5.shutdown()
    print("Conexión MT5 cerrada")

def is_market_open(symbol):
    """Verifica si el mercado está abierto para el símbolo."""
    info = mt5.symbol_info(symbol)
    if not info:
        return False
    return info.trade_mode in [mt5.SYMBOL_TRADE_MODE_FULL, mt5.SYMBOL_TRADE_MODE_CLOSEONLY]

def get_candles(symbol, timeframe, count):
    """
    Obtiene velas históricas con CAPTURA TOTAL DE EXCEPCIONES.
    Evita que MT5 rompa el bot.
    """
    try:
        # Seleccionar símbolo
        if not mt5.symbol_select(symbol, True):
            print(f"Advertencia: No se pudo seleccionar {symbol}")
            return None
        
        # Intentar obtener velas
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        
        # Verificar resultado
        if rates is None:
            print(f"Error: copy_rates_from_pos devolvió None para {symbol}")
            return None
        
        if len(rates) == 0:
            print(f"Advertencia: Sin datos históricos para {symbol}")
            return None
        
        # Convertir a diccionarios
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
        print(f"EXCEPCIÓN CAPTURADA en get_candles({symbol}): {e}")
        return None

def send_order(symbol, order_type, volume, price, sl=None, tp=None, comment=""):
    """Envía una orden de trading con validaciones."""
    if not is_market_open(symbol):
        print(f"Mercado cerrado para {symbol}")
        return None
    
    # Validar precio
    if price <= 0:
        print(f"Precio inválido para {symbol}: {price}")
        return None

    order = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 123456,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    
    result = mt5.order_send(order)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Error enviando orden en {symbol}: {result.retcode} - {result.comment}")
        return None
    
    print(f"Orden ejecutada #{result.order} | {symbol} | Vol: {volume} | Precio: {result.price}")
    return result.order

def close_position(ticket):
    """Cierra una posición por ticket con manejo de errores."""
    position = mt5.positions_get(ticket=ticket)
    if not position or len(position) == 0:
        print(f"Posición #{ticket} no encontrada")
        return False
    
    pos = position[0]
    symbol = pos.symbol
    volume = pos.volume
    tick = mt5.symbol_info_tick(symbol)
    
    if not tick:
        print(f"No se pudo obtener tick para {symbol}")
        return False
    
    price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    
    order = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": close_type,
        "position": ticket,
        "price": price,
        "deviation": 20,
        "magic": 123456,
        "comment": "Cierre automático",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    
    result = mt5.order_send(order)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        profit = result.profit if hasattr(result, 'profit') else pos.profit
        print(f"Posición #{ticket} cerrada | Profit: ${profit:.2f}")
        return True
    else:
        print(f"Error cerrando #{ticket}: {result.retcode} - {result.comment}")
        return False

def get_positions(symbol=None):
    """Obtiene posiciones abiertas con manejo de errores."""
    try:
        if symbol:
            return mt5.positions_get(symbol=symbol)
        return mt5.positions_get()
    except Exception as e:
        print(f"Error obteniendo posiciones: {e}")
        return []