from fastapi import FastAPI, Request  # type: ignore
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore
from banner import print_startup_banner
from datetime import datetime
from genres import format_genres_with_emojis
from logger_colors import LogColor

import atexit
import json
import os
import pytz
import random
import re
import requests
import sys
import threading
import urllib.parse
import uuid
import time

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
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
JELLYFIN_SERVER_NAME = CONFIG["jellyfin"].get("server_name", "Jellyfin")
JELLYFIN_SERVER_URL = CONFIG["jellyfin"].get("server_url")
JELLYFIN_API_KEY = CONFIG["jellyfin"].get("api_key")
WHATSAPP_BOT_NUMBER = CONFIG["whatsapp_bot_number"]
GROUP_INTERVAL = CONFIG.get("group_interval_seconds", 60)
START_HOUR = CONFIG.get("start_hour", 10)
END_HOUR = CONFIG.get("end_hour", 22)
TIMEZONE = pytz.timezone(CONFIG.get("timezone", "UTC"))
LANGUAGE = CONFIG.get("language", "es")
WHATSAPP_API = "http://127.0.0.1:3000/send-media"
IMDB_URL = f"https://www.imdb.com/{(LANGUAGE + '/') if LANGUAGE != 'en' else ''}title/{{}}"

if not all([JELLYFIN_SERVER_URL, JELLYFIN_API_KEY, WHATSAPP_BOT_NUMBER]):
    print(f"\n{LogColor.RED}💥 Missing required config values. Please check your 'config.json'{LogColor.RESET}")
    print(f"{LogColor.YELLOW}👉 Required keys: 'jellyfin.server_url', 'jellyfin.api_key', 'whatsapp_bot_number'\n{LogColor.RESET}")
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
    enabled_users = [user for user in users if user.get("enabled", True)]
    total_users = len(enabled_users)

    for index, user in enumerate(enabled_users):
        try:
            user_name = user.get("username", "")
            user_phone = user.get("phone")

            if not user_phone:
                print(f"{LogColor.YELLOW}⚠️ Skipping user '{user_name}' due to missing phone number{LogColor.RESET}")
                continue

            message = build_message(items, user_name=user_name, user_phone=user_phone)

            item_id = items[0].get("ItemId") or items[0].get("Id")
            poster_url = f"{JELLYFIN_SERVER_URL}/Items/{item_id}/Images/Primary?api_key={JELLYFIN_API_KEY}"

            print(f"{LogColor.BLUE}📬 Sending message to {user_name} ({user_phone})...{LogColor.RESET}")

            response = requests.post(
                WHATSAPP_API,
                json={"to": user_phone, "caption": message, "image_url": poster_url},
                timeout=15
            )

            if response.status_code != 200:
                print(f"{LogColor.RED}❌ Failed to send to {user_name}. WhatsApp response: {response.text}{LogColor.RESET}")
            else:
                print(f"{LogColor.GREEN}✅ Message sent to {user_name} successfully!{LogColor.RESET}")
        except Exception as e:
            print(f"{LogColor.RED}💥 WhatsApp error for {user_name}: {e}{LogColor.RESET}")
        
        if index < total_users - 1:
            apply_anti_ban_delay()

def apply_anti_ban_delay():
    seconds = random.randint(5, 20)
    print(f"{LogColor.CYAN}🛡️ Anti-ban shield: Waiting {seconds}s before next message...{LogColor.RESET}")
    time.sleep(seconds)

# =========================
# MESSAGE BUILDER
# =========================

def build_message(items, user_name="", user_phone=None):
    notification_id = str(uuid.uuid4())[:8]
    unsubscribe_link = ""

    if user_phone:
        unsubscribe_text = f"Unsubscribe {user_phone} - _{notification_id}_"
        encoded_text = urllib.parse.quote(unsubscribe_text)
        unsubscribe_spintax = resolve_spintax("{🚨 Darme de baja:|❌ Cancelar suscripción:|🔕 No recibir más avisos:}")
        unsubscribe_link = f"\n\n{unsubscribe_spintax} https://wa.me/{WHATSAPP_BOT_NUMBER}?text={encoded_text}"

    if len(items) == 1:
        item = items[0]

        title = item.get("Name", "Unknown Title")
        year = item.get("Year")
        year_str = f" ({year})" if year else ""
        genres = format_genres_with_emojis(item.get("Genres", "N/A"))
        imdb_id = item.get("Provider_imdb")
        imdb_url = f"\n\n🌐 {IMDB_URL.format(imdb_id)}" if imdb_id else ""

        message_template = (
            f"{{🍿 ¡Disponible ahora en {JELLYFIN_SERVER_NAME}!|🎬 ¡Estreno en la plataforma!|🎥 Mirá lo nuevo en Jellyfin}}\n\n"
            f"{{👋🏻 ¡Hola! |🎉 ¡Buenas! |✨ Hola, ¿cómo estás? }}{user_name}\n\n"
            f"🎞️ *{title}{year_str}*\n\n"
            f"{genres}{imdb_url}{unsubscribe_link}"
        )

        return resolve_spintax(message_template)
    else:
        titles = []
        for i in items:
            year = i.get("Year")
            year_str = f" ({year})" if year else ""
            titles.append(f"🎞️ *{i.get('Name', 'Unknown Title')}{year_str}*")

        message_template = (
            f"{{🍿 ¡Disponibles ahora en {JELLYFIN_SERVER_NAME}!|🎬 ¡Estrenos en la plataforma!|🎥 Mirá lo nuevo en Jellyfin}}\n\n"
            f"{{👋🏻 ¡Hola! |🎉 ¡Buenas! |✨ Hola, ¿cómo estás? }}{user_name}\n\n"
            f"{chr(10).join(titles)}{unsubscribe_link}"
        )

        return resolve_spintax(message_template)

def resolve_spintax(text: str) -> str:
    pattern = re.compile(r'\{([^{}]+)\}')
    while True:
        match = pattern.search(text)
        if not match:
            break
        options = match.group(1).split('|')
        text = text.replace(match.group(0), random.choice(options), 1)
    return text

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