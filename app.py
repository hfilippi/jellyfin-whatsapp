from fastapi import FastAPI, Request  # type: ignore
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore
from banner import print_startup_banner
from datetime import datetime
from genres import format_genres_with_emojis
from logger_colors import LogColor

import atexit
import json
import pytz
import requests
import sys
import threading

app = FastAPI()

# =========================
# LOAD CONFIG
# =========================

CONFIG_PATH = "/config/config.json"

try:
    with open(CONFIG_PATH, "r") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    print(f"\n{LogColor.RED}💥 Config file not found at '{CONFIG_PATH}'{LogColor.RESET}\n")
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f"\n{LogColor.RED}💥 Invalid JSON in config file '{CONFIG_PATH}': {e}{LogColor.RESET}\n")
    sys.exit(1)
except Exception as e:
    print(f"\n{LogColor.RED}💥 Failed to load config file '{CONFIG_PATH}': {e}{LogColor.RESET}\n")
    sys.exit(1)

APP_NAME = CONFIG.get("app_name", "Notifier")
APP_VERSION = CONFIG.get("app_version", "N/A")
JELLYFIN_URL = CONFIG["jellyfin_url"]
API_KEY = CONFIG["api_key"]
BOT_NUMBER = CONFIG["bot_number"]
GROUP_INTERVAL = CONFIG.get("group_interval_seconds", 60)
START_HOUR = CONFIG.get("start_hour", 10)
END_HOUR = CONFIG.get("end_hour", 22)
TIMEZONE = pytz.timezone(CONFIG.get("timezone", "UTC"))
LANGUAGE = CONFIG.get("language", "en")
WHATSAPP_API = "http://127.0.0.1:3000/send-media"
IMDB_URL = f"https://www.imdb.com/{LANGUAGE}/title/{{}}"

if not all([JELLYFIN_URL, API_KEY, BOT_NUMBER]):
    print(f"\n{LogColor.RED}💥 Missing required config values. Please check your 'config.json'{LogColor.RESET}")
    print(f"{LogColor.YELLOW}👉 Required keys: 'jellyfin_url', 'api_key', 'bot_number'\n{LogColor.RESET}")
    sys.exit(1)

# =========================
# LOAD USERS
# =========================

def load_users():
    with open("/config/users.json", "r") as f:
        return json.load(f)

# =========================
# STATE
# =========================

pending_items = []
lock = threading.Lock()
scheduler = BackgroundScheduler()

@app.on_event("startup")
def start_scheduler():
    print_startup_banner(APP_NAME, APP_VERSION)

    trigger = IntervalTrigger(
        seconds=GROUP_INTERVAL,
        start_date=datetime.now(TIMEZONE),
        timezone=TIMEZONE
    )

    scheduler.add_job(
        process_pending,
        trigger=trigger,
        id="process_pending",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30
    )
    
    scheduler.start()
    print(f"{LogColor.GREEN}🟢 Scheduler started! Running every {GROUP_INTERVAL}s between {START_HOUR}:00h and {END_HOUR}:00h{LogColor.RESET}")

@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown()
    print(f"{LogColor.RED}🔴 Scheduler stopped{LogColor.RESET}")

# =========================
# MESSAGE BUILDER
# =========================

def build_message(items, user_phone=None):
    unsubscribe_link = ""
    if user_phone:
        unsubscribe_link = f"\n🔕 Darme de baja: https://wa.me/{BOT_NUMBER}?text=Salir%20{user_phone}"

    if len(items) == 1:
        item = items[0]

        title = item.get("Name", "Unknown Title")
        year = item.get("Year")
        year_str = f" ({year})" if year else ""
        genres = format_genres_with_emojis(item.get("Genres", "N/A"))
        imdb_id = item.get("Provider_imdb")
        imdb_url = f"\n🌐 {IMDB_URL.format(imdb_id)}\n" if imdb_id else ""

        return f"""🍿 ¡Disponible ahora en Raspiflix!

🎬 *{title}{year_str}*

{genres}{imdb_url}{unsubscribe_link}"""
    else:
        lines = []
        for i in items:
            year = i.get("Year")
            year_str = f" ({year})" if year else ""
            lines.append(f"🎬 *{i.get('Name', 'Unknown Title')}{year_str}*")

        return f"""🍿 ¡Disponibles ahora en Raspiflix!

{chr(10).join(lines)}{unsubscribe_link}"""

# =========================
# PROCESSOR
# =========================

def process_pending():
    global pending_items
    
    now_local = datetime.now(TIMEZONE)
    current_hour = now_local.hour

    if not (START_HOUR <= current_hour < END_HOUR):
        return

    with lock:
        if not pending_items:
            return

        print(f"{LogColor.CYAN}📊 Processing {len(pending_items)} Pending items...{LogColor.RESET}")

        items = pending_items.copy()
        pending_items.clear()
    
    users = load_users()

    for user in users:
        if not user.get("enabled", True):
            print(f"{LogColor.YELLOW}🔕 Skipping {user['username']} (disabled){LogColor.RESET}")
            continue
        try:
            message = build_message(items, user_phone=user["phone"])

            first_item = items[0]
            item_id = first_item.get("ItemId")
            poster_url = f"{JELLYFIN_URL}/Items/{item_id}/Images/Primary?api_key={API_KEY}"

            print(f"{LogColor.BLUE}📬 Sending message to {user['username']} ({user['phone']})...{LogColor.RESET}")

            response = requests.post(
                WHATSAPP_API,
                json={"to": user["phone"], "caption": message, "image_url": poster_url},
                timeout=15
            )

            if response.status_code != 200:
                print(f"{LogColor.RED}❌ Failed to send to {user['username']}. WhatsApp response: {response.text}{LogColor.RESET}")
            else:
                print(f"{LogColor.GREEN}✅ Message sent to {user['username']} successfully!{LogColor.RESET}")
        except Exception as e:
            print(f"{LogColor.RED}💥 WhatsApp error for {user['username']}: {e}{LogColor.RESET}")

# =========================
# ENDPOINTS
# =========================

@app.get("/")
async def health():
    return {"status": "ok"}

@app.get("/users")
async def get_users():
    return load_users()

@app.post("/jellyfin")
async def jellyfin_webhook(request: Request):
    data = await request.json()
    notification_type = data.get("NotificationType")

    if notification_type != "ItemAdded":
        print(f"{LogColor.YELLOW}⚠️ Ignored notification type: {notification_type}{LogColor.RESET}")
        return {"ignored": True}

    with lock:
        pending_items.append(data)

    name = data.get("Name", "Unknown Title")
    year = data.get("Year")
    year_str = f" ({year})" if year else ""

    print(f'{LogColor.CYAN}📥 Queued: "{name}{year_str}" | Total: {len(pending_items)}{LogColor.RESET}')

    return {"queued": True}

atexit.register(lambda: scheduler.shutdown())