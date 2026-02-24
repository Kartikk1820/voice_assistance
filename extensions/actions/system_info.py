defination = '''
function system_info(query: str) -> str:

arguments:
- query: The system info to fetch. One of: "cpu", "ram", "battery", "all"

Example usage:
system_info("cpu")
system_info("ram")
system_info("battery")
system_info("all")
'''

import os
import psutil
from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

def system_info(query: str) -> str:
    query = query.lower().strip()

    def get_cpu():
        cpu = psutil.cpu_percent(interval=1)
        cores = psutil.cpu_count()
        return f"CPU Usage: {cpu}% | Cores: {cores}"

    def get_ram():
        ram = psutil.virtual_memory()
        total = round(ram.total / (1024**3), 2)
        used = round(ram.used / (1024**3), 2)
        percent = ram.percent
        return f"RAM: {used}GB used / {total}GB total ({percent}%)"

    def get_battery():
        battery = psutil.sensors_battery()
        if battery is None:
            return "Battery: No battery found (desktop PC)."
        percent = battery.percent
        charging = "Charging" if battery.power_plugged else "Not Charging"
        time_left = ""
        if not battery.power_plugged and battery.secsleft != psutil.POWER_TIME_UNLIMITED:
            mins = battery.secsleft // 60
            time_left = f" | Time left: {mins} min"
        return f"Battery: {percent}% | {charging}{time_left}"

    if query == "cpu":
        return get_cpu()
    elif query == "ram":
        return get_ram()
    elif query == "battery":
        return get_battery()
    elif query == "all":
        return f"{get_cpu()}\n{get_ram()}\n{get_battery()}"
    else:
        return f"Unknown query '{query}'. Use: cpu, ram, battery, all."


if __name__ == "__main__":
    print(system_info("all"))