# main.py
import sys
import importlib
import os

BOTS_DIR = os.path.join(os.path.dirname(__file__), "bots")

def load_bot(bot_name):
    """
    Busca automáticamente un bot dentro de /bots/ y carga su módulo.
    Debe tener una función run() o run_<botname>().
    """
    bot_file = f"{bot_name}.py"
    bot_path = os.path.join(BOTS_DIR, bot_file)

    if not os.path.exists(bot_path):
        print(f"❌ Bot '{bot_name}' no encontrado en /bots/")
        print("Bots disponibles:", list_available_bots())
        return None

    try:
        module = importlib.import_module(f"bots.{bot_name}")
        return module
    except Exception as e:
        print(f"❌ Error cargando el bot {bot_name}: {e}")
        return None


def list_available_bots():
    """
    Lista todos los archivos .py dentro de /bots/ excepto __init__.py
    """
    return [
        f.replace(".py", "")
        for f in os.listdir(BOTS_DIR)
        if f.endswith(".py") and f != "__init__.py"
    ]


def main():
    if len(sys.argv) < 2:
        print("Uso: py main.py <botname>")
        print("Bots disponibles:", list_available_bots())
        sys.exit(1)

    bot_name = sys.argv[1].lower()

    module = load_bot(bot_name)
    if module is None:
        sys.exit(1)

    # prioridad 1 → función run()
    if hasattr(module, "run"):
        module.run()
        return

    # prioridad 2 → función run_<botname>()
    fn_name = f"run_{bot_name}"
    if hasattr(module, fn_name):
        getattr(module, fn_name)()
        return

    print(f"❌ El bot '{bot_name}' no tiene función run() ni {fn_name}().")


if __name__ == "__main__":
    main()
