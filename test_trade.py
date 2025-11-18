import MetaTrader5 as mt5
from time import sleep
from datetime import datetime

# === CONFIG ===
LOGIN = 1600048003
PASSWORD = "1IAgenesis1!"
SERVER = "OANDA-Demo-1"
symbol = "EURUSD.sml"

# === CONEXIÓN ===
print("Conectando a MT5...")
if not mt5.initialize(login=LOGIN, password=PASSWORD, server=SERVER):
    print("Error de conexión:", mt5.last_error())
    quit()
print("✅ Conectado!")

if not mt5.symbol_select(symbol, True):
    print("No se pudo seleccionar símbolo")
    mt5.shutdown()
    quit()

# === FUNCIÓN: ¿Puedo operar ahora? ===
def puedo_operar():
    # 1. Verificar trade_mode
    info = mt5.symbol_info(symbol)
    if info.trade_mode not in [0, 4]:  # FULL (0) o DEAL_ONLY (4)
        return False, f"trade_mode inválido: {info.trade_mode}"

    # 2. Verificar precios en vivo (bid/ask > 0)
    tick = mt5.symbol_info_tick(symbol)
    if tick is None or tick.bid <= 0 or tick.ask <= 0:
        return False, "Precios no en vivo"

    # 3. Verificar horario (OANDA: dom 18:05 CO a vie 17:59 CO)
    now = datetime.now()
    hora_co = now.hour + now.minute / 60.0  # Hora decimal CO (-05)
    dia_semana = now.weekday()  # 0=lun, 6=dom

    if dia_semana == 5:  # Sábado
        return False, "Sábado: mercado cerrado"
    if dia_semana == 6 and hora_co < 18.083:  # Domingo antes de 18:05 CO
        minutos_faltan = int((18.083 - hora_co) * 60)
        return False, f"Domingo: abre a las 18:05 CO. Faltan ~{minutos_faltan} min"
    if dia_semana < 5 and (hora_co < 0 or hora_co > 23.983):  # Lun-jue: todo el día
        pass  # OK
    if dia_semana == 4 and hora_co > 17.983:  # Viernes después de 17:59 CO
        return False, "Viernes después de cierre (17:59 CO)"

    return True, "¡TODO LISTO! Mercado abierto y trading permitido"

# === BUCLE: Esperar y operar ===
print("Verificando mercado...")
intentos = 0
max_intentos = 5  # Reintentos si falla el envío

while True:
    puedo, mensaje = puedo_operar()
    ahora = datetime.now().strftime("%H:%M:%S CO")
    print(f"[{ahora}] {mensaje}")

    if puedo:
        # === OBTENER PRECIO ===
        tick = mt5.symbol_info_tick(symbol)
        print(f"Precio - Bid: {tick.bid:.5f}, Ask: {tick.ask:.5f}")

        # === ORDEN DE MERCADO (FOK para OANDA) ===
        point = mt5.symbol_info(symbol).point
        price = tick.ask
        sl = price - 100 * point
        tp = price + 200 * point

        order = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": 0.01,
            "type": mt5.ORDER_TYPE_BUY,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 123456,
            "comment": "OANDA-AUTO-OPEN",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,  # FOK para OANDA
        }

        # === ENVIAR ORDEN (con reintentos) ===
        exito = False
        for intento in range(max_intentos):
            print(f"Enviando orden... (intento {intento+1}/{max_intentos})")
            result = mt5.order_send(order)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"✅ ¡ÉXITO! Posición #{result.order} a {result.price:.5f}")
                print(f"   SL: {sl:.5f} | TP: {tp:.5f}")
                exito = True
                break
            else:
                print(f"❌ Error {result.retcode}: {result.comment}")
                if intento < max_intentos - 1:
                    sleep(5)  # Espera 5s antes de retry

        if exito:
            # Mostrar posición
            positions = mt5.positions_get(symbol=symbol)
            if positions:
                for p in positions:
                    print(f"Posición activa: #{p.ticket} | Vol: {p.volume} | Profit: {p.profit:.2f}")
            break  # Sale del bucle

    else:
        sleep(60)  # Espera 1 min

# === CIERRE ===
sleep(3)
print("Cerrando conexión...")
mt5.shutdown()