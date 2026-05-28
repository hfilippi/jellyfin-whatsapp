[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Node.js](https://img.shields.io/badge/Node.js-18%2B-339933?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org/)
[![Docker](https://img.shields.io/badge/Docker-Container-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Jellyfin](https://img.shields.io/badge/Media_Server-Jellyfin-magenta?style=for-the-badge&logo=jellyfin&logoColor=white&labelColor=AA5CC4)](https://jellyfin.org/)

# 🍿 jellyfin-whatsapp

A decoupled, lightweight notification engine built for Raspberry Pi to automatically aggregate newly added media from **Jellyfin** and send structured updates with official poster art to users via **WhatsApp**.

---

## 🏗️ Architecture & Ecosystem

The system features a **decoupled architecture** split into two main containerized microservices sharing a common data directory (`/config`). This design keeps memory footprints exceptionally low on single-board computers like the Raspberry Pi.

* **Backend Engine (`Python / FastAPI`):** Receives instant webhooks from Jellyfin when media is added, buffers requests to prevent message spamming, enforces timezone-aware quiet hours, and matches media profiles with local database users.
* **Gateway Service (`Node.js / whatsapp-web.js`):** Acts as a headless WhatsApp Web client instance. It listens for outgoing data requests from the Python engine to forward media payloads and monitors chat interaction for instant subscription opt-outs.

---

## 🚀 Key Features

* **Smart Message Aggregation:** Instead of flooding users with single texts when a season of a TV show indexes, notifications are batched into a single unified broadcast based on a configurable interval window.
* **Quiet Hours Shield:** Automatically holds back notifications received during late-night hours. Pending media aggregates silently in memory and flushes immediately as a single summary once morning hours kick in.
* **One-Click Unsubscribe Link:** Every single notification message attaches a dynamically-built, native WhatsApp deep-link (`wa.me`) passing a unique cancellation payload. 
* **Local-First Architecture:** Eliminates complex database management. Subscriptions and runtime parameters are fully handled via lightweight, localized, system-synced JSON layers.

---

## 📂 File Structure

```text
├── app/
│   ├── app.py                  # Main FastAPI Application & Scheduling logic
│   ├── banner.py               # Custom ASCII branding initialization module
│   ├── genres.py               # Media genre categorization to Emoji adapter 
│   ├── logger_colors.py        # Thread-safe ANSI terminal log colorizer
│   └── requirements.txt        # Python library dependencies
├── server/
│   ├── server.js               # Node.js gateway & headless whatsapp-web client
│   └── package.json            # Node.js library dependencies
└── config/                     # Shared Docker Shared Volume
    ├── config.json             # Core infrastructure & scheduler rules setup
    └── users.json              # Local subscription storage database mapping
```

---

## ⚙️ Configuration Setup

Both environments read core parameters from a single setup file in `/config/config.json`.

```json
{
    "app_name": "Notifications Engine",
    "app_version": "1.0.0",
    "jellyfin_url": "http://YOUR_SERVER_URL_HERE:YOUR_PORT_HERE",
    "api_key": "YOUR_JELLYFIN_API_KEY_HERE",
    "bot_number": "YOUR_PHONE_NUMBER_HERE",
    "group_interval_seconds": 60,
    "start_hour": 10,
    "end_hour": 22,
    "timezone": "America/Argentina/Buenos_Aires",
    "language": "es"
}
```

### 📱 `bot_number` format

- **2 digits** for international country code.
- **1 digit**  for mobile prefix required for international calls mobile lines.
- **2 digits** for Area code.
- **8 digits** for unique 8-digit local subscriber number.

---

## 👥 User Subscription Mapping (`/config/users.json`)

Control access manually by populating your subscriber base within this directory structure.

### 🇦🇷 Argentinian phone number examples

```json
[
    {
        "username": "admin",
        "phone": "5491155555555",
        "enabled": true
    },
    {
        "username": "guest",
        "phone": "5491100000000",
        "enabled": false
    }
]
```

---

## 🔄 Core Workflows

### 📥 1. Media Webhook Processing

- Jellyfin triggers an `ItemAdded event` and sends a payload to FastAPI (`POST /jellyfin`).
- The payload is securely staged into a thread-safe memory registry pending_items.

### ⏱️ 2. Time-Restricted Aggregator (`Scheduler`)

- The background scheduler evaluates runtime intervals.
- It tracks the designated zone-aware hours (`start_hour` and `end_hour`).
- If it runs out-of-bounds (e.g., 3:00 AM), it safely suspends processing. Staged content remains buffered until the morning.
- When boundaries clear, the content compiles into a single custom design message containing official media posters and automatically forwards it to all users marked "enabled": true.

### 🔕 3. Unsubscribe Lifecycle

- The user clicks the built-in deep link inside their WhatsApp notification message:
https://wa.me/{bot_number}?text=Salir%20{user_phone}
- The user sends the pre-filled text.
- The Node.js service intercepts the command "salir <phone>".
- It reads `/config/users.json`, searches for the target number, and flips their permission key to "enabled": false.
- The Python engine instantly recognizes the status mutation on the subsequent iteration loop and skips sending upcoming packages.

---

## 🛠️ Diagnostics & Terminal Logging

Terminal execution traces utilize decoupled visual states via explicit ANSI escape logs to maintain ease of maintenance inside remote server dashboards like Portainer:

- 🟢 GREEN: Successful engine components initialization and automated job completion status codes.
- 🔵 BLUE: Outgoing messaging actions targeting remote client connections.
- 🟡 YELLOW: Security exemptions, system skips, or users containing disabled permission flags.
- 🔴 RED: Formatting issues, invalid configuration inputs, or critical system exceptions.

---