from datetime import datetime


def on_config(config):
    config["copyright"] = f"Copyright &copy; 2024-{datetime.now().year} CCI Bonn"
    return config
