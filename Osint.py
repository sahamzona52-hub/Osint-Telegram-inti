#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║   RED PHANTOM OSINT — MANUAL INPUT + FULL READ EDITION               ║
║   Input target manual · Baca semua data · Export lengkap            ║
║   Powered by Yusiqo · Untuk penggunaan yang SAH & BERIZIN saja      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import re
import json
import csv
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

from pyrogram import Client
from pyrogram.errors import (
    PeerIdInvalid, UsernameInvalid, UsernameNotOccupied,
    FloodWait, ChatAdminRequired, UserNotParticipant,
    ChannelPrivate, ChatForbidden, AuthKeyUnregistered,
)
from pyrogram.types import User
from pyfiglet import figlet_format
from termcolor import colored


# ══════════════════════════════════════════════════════════════════
# GLOBAL
# ══════════════════════════════════════════════════════════════════
CONFIG_FILE   = "config.json"
REPORT_DIR    = Path("reports")
MEDIA_DIR     = REPORT_DIR / "media"
HISTORY_DIR   = Path("history")

RED           = "red"
BRIGHT_RED    = "light_red"


# ══════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════
def cprint(text, color=BRIGHT_RED, attrs=None):
    try:
        print(colored(text, color, attrs=attrs))
    except Exception:
        print(text)


def banner():
    os.system("clear" if os.name == "posix" else "cls")
    art = figlet_format("RED PHANTOM", font="slant")
    cprint(art, RED, attrs=["bold"])
    line = "═" * 64
    cprint(f"  {line}", RED)
    cprint("   ⚡  TELEGRAM OSINT · MANUAL INPUT · FULL READ  ⚡", RED, attrs=["bold"])
    cprint(f"  {line}", RED)
    cprint("   ▸ Tool    : Red Phantom — Full Read", BRIGHT_RED)
    cprint("   ▸ Author  : Yusiqo", BRIGHT_RED)
    cprint("   ▸ Mode    : Input manual + baca semua yang bisa diakses", BRIGHT_RED)
    cprint(f"  {line}\n", RED)


def section(title, icon="◆"):
    line = "─" * 62
    cprint(f"\n┌{line}┐", RED)
    cprint(f"│ {icon} {title.upper():<59}│", RED, attrs=["bold"])
    cprint(f"└{line}┘", RED)


def kv(label, value, value_color="white"):
    left  = colored(f"    ▹ {label:<18}: ", BRIGHT_RED, attrs=["bold"])
    right = colored(str(value), value_color)
    print(f"{left}{right}")


def status(tag, message, color=BRIGHT_RED):
    print(colored(f"  [{tag}] ", color, attrs=["bold"]) + colored(message, "white"))


def success(msg):  status("✔", msg, "green")
def warn(msg):     status("!", msg, "yellow")
def error(msg):    status("✘", msg, RED)
def info(msg):     status("›", msg, BRIGHT_RED)


def progress_bar(i, total, prefix="", length=30):
    filled = int(length * i // total) if total else length
    bar = "█" * filled + "░" * (length - filled)
    print(colored(f"\r  {prefix} |{bar}| {i}/{total}", RED), end="", flush=True)
    if i >= total:
        print()


def ask(prompt, default=None, allow_empty=False):
    """Prompt input manual dengan validasi."""
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(colored(f"  ▸ {prompt}{suffix}: ", BRIGHT_RED)).strip()
        if not raw:
            if default is not None:
                return default
            if allow_empty:
                return ""
            warn("Input tidak boleh kosong.")
            continue
        return raw


def ask_yes_no(prompt, default="n"):
    raw = input(colored(f"  ▸ {prompt} (y/n) [{default}]: ", BRIGHT_RED)).strip().lower()
    if not raw:
        raw = default
    return raw in ("y", "yes", "1", "true")


def ask_int(prompt, default=None, min_val=0):
    while True:
        raw = input(colored(f"  ▸ {prompt}" + (f" [{default}]" if default is not None else "") + ": ",
                            BRIGHT_RED)).strip()
        if not raw and default is not None:
            return default
        try:
            v = int(raw)
            if v < min_val:
                warn(f"Nilai minimal {min_val}")
                continue
            return v
        except ValueError:
            warn("Harus angka.")


# ══════════════════════════════════════════════════════════════════
# KONFIGURASI API
# ══════════════════════════════════════════════════════════════════
def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            error("config.json rusak, buat baru.")
    return {}


def save_config(api_id, api_hash, session_name):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"api_id": api_id, "api_hash": api_hash,
                   "session_name": session_name}, f, indent=4)
    success("Konfigurasi tersimpan.")


def get_config() -> dict:
    config = load_config()
    section("Konfigurasi API Telegram", "⚙")
    if config.get("api_id") and config.get("api_hash") and config.get("session_name"):
        kv("API ID",  config["api_id"], RED)
        kv("Session", config["session_name"], RED)
        if ask_yes_no("Gunakan konfigurasi ini?", "y"):
            return config

    warn("Ambil API di https://my.telegram.org/apps")
    api_id   = ask("API ID")
    api_hash = ask("API Hash")
    session  = ask("Session name", default="red_phantom")
    save_config(api_id, api_hash, session)
    return {"api_id": api_id, "api_hash": api_hash, "session_name": session}


# ══════════════════════════════════════════════════════════════════
# MENU UTAMA
# ══════════════════════════════════════════════════════════════════
def main_menu() -> dict:
    """Tampilkan menu pilihan scrape."""
    section("Menu Scrape — Pilih yang Diinginkan", "☰")
    print(colored("    1. Full Read (semua di bawah, kecuali monitor)", BRIGHT_RED))
    print(colored("    2. Profile + Bio + Photos", BRIGHT_RED))
    print(colored("    3. Common Groups + Messages", BRIGHT_RED))
    print(colored("    4. Private Chat History", BRIGHT_RED))
    print(colored("    5. Mention Analysis (cross-group)", BRIGHT_RED))
    print(colored("    6. Activity Analysis", BRIGHT_RED))
    print(colored("    7. Saved Messages (operator)", BRIGHT_RED))
    print(colored("    8. Contacts (operator)", BRIGHT_RED))
    print(colored("    9. Real-time Monitor", BRIGHT_RED))
    print(colored("    0. Keluar", BRIGHT_RED))

    choice = ask("Pilihan (1-9, 0=keluar)", default="1")

    presets = {
        "1": {"profile": True, "photos": True, "groups": True,
              "private": True, "mentions": True, "activity": True,
              "saved": True, "contacts": True, "monitor": False},
        "2": {"profile": True, "photos": True, "groups": False,
              "private": False, "mentions": False, "activity": False,
              "saved": False, "contacts": False, "monitor": False},
        "3": {"profile": True, "photos": False, "groups": True,
              "private": False, "mentions": False, "activity": True,
              "saved": False, "contacts": False, "monitor": False},
        "4": {"profile": True, "photos": False, "groups": False,
              "private": True, "mentions": False, "activity": True,
              "saved": False, "contacts": False, "monitor": False},
        "5": {"profile": True, "photos": False, "groups": True,
              "private": False, "mentions": True, "activity": False,
              "saved": False, "contacts": False, "monitor": False},
        "6": {"profile": True, "photos": False, "groups": True,
              "private": True, "mentions": False, "activity": True,
              "saved": False, "contacts": False, "monitor": False},
        "7": {"profile": False, "photos": False, "groups": False,
              "private": False, "mentions": False, "activity": False,
              "saved": True, "contacts": False, "monitor": False},
        "8": {"profile": False, "photos": False, "groups": False,
              "private": False, "mentions": False, "activity": False,
              "saved": False, "contacts": True, "monitor": False},
        "9": {"profile": True, "photos": False, "groups": False,
              "private": False, "mentions": False, "activity": False,
              "saved": False, "contacts": False, "monitor": True},
        "0": None,
    }
    return presets.get(choice)


# ══════════════════════════════════════════════════════════════════
# RESOLVER TARGET
# ══════════════════════════════════════════════════════════════════
async def resolve_target(client: Client):
    """Input manual target: username, ID, atau nomor HP."""
    section("Input Target (Manual)", "🎯")
    print(colored("    Format yang diterima:", BRIGHT_RED))
    print(colored("      • @username         contoh: @johndoe", "white"))
    print(colored("      • username          contoh: johndoe", "white"))
    print(colored("      • ID numerik        contoh: 123456789", "white"))
    print(colored("      • Nomor HP          contoh: +6281234567890", "white"))

    raw = ask("Target")
    raw = raw.strip()

    # Normalisasi
    if raw.startswith("@"):
        candidate = raw
    elif raw.replace("+", "").replace("-", "").replace(" ", "").isdigit() and len(raw) > 8:
        candidate = raw if raw.startswith("+") else "+" + raw.lstrip("+")
    elif raw.isdigit():
        candidate = int(raw)
    else:
        candidate = raw

    info(f"Resolve target: {candidate}")
    try:
        user = await client.get_users(candidate)
        success(f"OK → {user.first_name} {user.last_name or ''} (@{user.username or 'None'}) — ID: {user.id}")
        return user
    except (PeerIdInvalid, UsernameInvalid, UsernameNotOccupied):
        error(f"Target '{raw}' tidak ditemukan / tidak valid.")
        if ask_yes_no("Coba target lain?", "y"):
            return await resolve_target(client)
        return None
    except FloodWait as fw:
        warn(f"FloodWait {fw.value}s")
        await asyncio.sleep(fw.value)
        return await resolve_target(client)
    except Exception as e:
        error(f"Error: {e}")
        if ask_yes_no("Coba lagi?", "y"):
            return await resolve_target(client)
        return None


# ══════════════════════════════════════════════════════════════════
# FULL PROFILE READ
# ══════════════════════════════════════════════════════════════════
async def read_profile(client: Client, user: User) -> dict:
    """Baca semua field profil yang bisa diakses."""
    section("Full Profile Read", "🎯")

    # Refresh untuk data terbaru
    try:
        user = await client.get_users(user.id)
    except Exception:
        pass

    data = {
        "id":           user.id,
        "username":     user.username,
        "first_name":   user.first_name,
        "last_name":    user.last_name,
        "phone":        user.phone_number,
        "dc_id":        user.dc_id,
        "language":     user.language_code,
        "status":       str(user.status) if user.status else None,
        "bio":          getattr(user, "bio", None),
        "is_bot":       user.is_bot,
        "is_verified":  user.is_verified,
        "is_premium":   getattr(user, "is_premium", False),
        "is_restricted": user.is_restricted,
        "is_scam":      user.is_scam,
        "is_fake":      user.is_fake,
        "is_support":   getattr(user, "is_support", False),
        "is_contact":   user.is_contact if hasattr(user, "is_contact") else None,
        "is_mutual_contact": user.is_mutual_contact if hasattr(user, "is_mutual_contact") else None,
        "is_deleted":   user.is_deleted if hasattr(user, "is_deleted") else None,
        "photo":        None,
    }

    if user.photo:
        data["photo"] = {
            "small_file_id": user.photo.small_file_id,
            "big_file_id":   user.photo.big_file_id,
            "dc_id":         user.photo.dc_id,
        }

    # Tampilkan
    kv("ID",        data["id"], RED)
    kv("Username",  f"@{data['username']}" if data["username"] else "None", RED)
    kv("First Name", data["first_name"] or "None")
    kv("Last Name", data["last_name"] or "None")
    kv("Phone",     data["phone"] or "Hidden", "yellow")
    kv("DC ID",     data["dc_id"])
    kv("Language",  data["language"] or "None")
    kv("Status",    data["status"] or "None")
    kv("Bio",       data["bio"] or "None", "cyan")
    print()
    kv("Bot",       "Yes" if data["is_bot"] else "No")
    kv("Verified",  "Yes" if data["is_verified"] else "No", "cyan")
    kv("Premium",   "Yes" if data["is_premium"] else "No", "cyan")
    kv("Support",   "Yes" if data["is_support"] else "No")
    kv("Contact",   data["is_contact"] if data["is_contact"] is not None else "N/A")
    kv("Mutual",    data["is_mutual_contact"] if data["is_mutual_contact"] is not None else "N/A")
    kv("Deleted",   data["is_deleted"] if data["is_deleted"] is not None else "N/A")
    kv("Restricted", "Yes" if data["is_restricted"] else "No")
    kv("Scam",      "Yes" if data["is_scam"] else "No", "red" if data["is_scam"] else "white")
    kv("Fake",      "Yes" if data["is_fake"] else "No", "red" if data["is_fake"] else "white")
    kv("Has Photo", "Yes" if data["photo"] else "No")

    return data


async def read_profile_photos(client: Client, user: User, limit=20,
                              download=False) -> list:
    section("Profile Photos", "📸")
    photos = []
    try:
        async for photo in client.get_chat_photos(user.id, limit=limit):
            entry = {
                "date":    str(photo.date),
                "file_id": photo.file_id,
                "dc_id":   photo.dc_id,
                "local_path": None,
            }
            kv("Photo", f"{photo.date} | dc={photo.dc_id} | {photo.file_id[:22]}...")
            if download:
                try:
                    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                    fname = f"profile_{user.id}_{photo.date.strftime('%Y%m%d_%H%M%S')}.jpg"
                    path = await client.download_media(
                        photo.file_id, file_name=str(MEDIA_DIR / fname))
                    if path:
                        entry["local_path"] = str(path)
                        success(f"↓ {path}")
                except Exception as e:
                    warn(f"Gagal download: {e}")
            photos.append(entry)
        if not photos:
            warn("Tidak ada foto profil publik.")
    except Exception as e:
        error(f"Gagal ambil foto: {e}")
    return photos


# ══════════════════════════════════════════════════════════════════
# GEO PARSER
# ══════════════════════════════════════════════════════════════════
COUNTRY_HINTS = {
    "indonesia": "Indonesia", "jakarta": "Indonesia", "bandung": "Indonesia",
    "surabaya": "Indonesia", "bali": "Indonesia", "medan": "Indonesia",
    "yogyakarta": "Indonesia", "semarang": "Indonesia", "makassar": "Indonesia",
    "singapore": "Singapore", "malaysia": "Malaysia", "kuala lumpur": "Malaysia",
    "thailand": "Thailand", "bangkok": "Thailand", "vietnam": "Vietnam",
    "philippines": "Philippines", "manila": "Philippines",
    "japan": "Japan", "tokyo": "Japan", "osaka": "Japan",
    "korea": "South Korea", "seoul": "South Korea",
    "china": "China", "beijing": "China", "shanghai": "China",
    "india": "India", "delhi": "India", "mumbai": "India",
    "usa": "USA", "united states": "USA", "new york": "USA",
    "california": "USA", "uk": "UK", "london": "UK",
    "germany": "Germany", "berlin": "Germany",
    "france": "France", "paris": "France",
    "spain": "Spain", "madrid": "Spain",
    "italy": "Italy", "rome": "Italy",
    "russia": "Russia", "moscow": "Russia",
    "australia": "Australia", "sydney": "Australia",
    "canada": "Canada", "toronto": "Canada",
    "brazil": "Brazil", "mexico": "Mexico",
    "turkey": "Turkey", "istanbul": "Turkey",
    "dubai": "UAE", "saudi": "Saudi Arabia",
}


def geo_from_bio(bio: str) -> dict:
    result = {"coordinates": None, "maps_link": None, "country": None,
              "city": None, "hits": []}
    if not bio:
        return result
    bio_l = bio.lower()

    m = re.search(r"(-?\d{1,3}\.\d+)\s*[,;\s]\s*(-?\d{1,3}\.\d+)", bio)
    if m:
        try:
            lat, lon = float(m.group(1)), float(m.group(2))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                result["coordinates"] = {"lat": lat, "lon": lon}
                result["maps_link"] = f"https://maps.google.com/?q={lat},{lon}"
        except ValueError:
            pass

    mm = re.search(
        r"(https?://(?:www\.)?(?:maps\.google\.com|goo\.gl/maps|maps\.app\.goo\.gl|yandex\.com/maps)[^\s]*)",
        bio,
    )
    if mm:
        result["maps_link"] = mm.group(1)

    for hint, country in COUNTRY_HINTS.items():
        if hint in bio_l:
            result["hits"].append(hint)
            if not result["country"]:
                result["country"] = country
            if hint != country.lower() and not result["city"]:
                result["city"] = hint.title()
    return result


def show_geo(geo: dict):
    section("Geolocation (dari bio)", "🌍")
    if not any([geo["coordinates"], geo["maps_link"], geo["country"], geo["city"]]):
        warn("Tidak ada info lokasi di bio.")
        return
    if geo["coordinates"]:
        kv("Coordinates", f"{geo['coordinates']['lat']}, {geo['coordinates']['lon']}", RED)
    if geo["maps_link"]:
        kv("Maps Link",   geo["maps_link"], "cyan")
    if geo["country"]:
        kv("Country",     geo["country"], RED)
    if geo["city"]:
        kv("City",        geo["city"])
    if geo["hits"]:
        kv("Hints",       ", ".join(geo["hits"]), "yellow")


# ══════════════════════════════════════════════════════════════════
# USERNAME HISTORY
# ══════════════════════════════════════════════════════════════════
def track_username(user: User) -> dict:
    section("Username History", "🔗")
    HISTORY_DIR.mkdir(exist_ok=True)
    file = HISTORY_DIR / f"user_{user.id}.json"

    entry = {
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "username":   user.username,
        "first_name": user.first_name,
        "last_name":  user.last_name,
        "phone":      user.phone_number,
        "bio":        getattr(user, "bio", None),
    }
    history = []
    if file.exists():
        try:
            history = json.load(open(file))
        except Exception:
            history = []

    prev = [h.get("username") for h in history if h.get("username")]
    changed = (not history) or (history[-1].get("username") != user.username)

    history.append(entry)
    with open(file, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False, default=str)

    kv("Current",   f"@{user.username}" if user.username else "None", RED)
    kv("Snapshots", len(history))
    if prev:
        kv("Previous",  ", ".join(f"@{u}" for u in set(prev)))
    if changed and len(history) > 1:
        warn("Username BERUBAH sejak snapshot terakhir!")
    elif changed:
        info("Snapshot pertama disimpan.")
    return {"current": user.username, "history": history, "changed": changed}


# ══════════════════════════════════════════════════════════════════
# MEDIA HELPER
# ══════════════════════════════════════════════════════════════════
async def try_download(client: Client, message, user_id: int, max_mb=20) -> str | None:
    if not message.media:
        return None
    size_mb = 0
    for attr in ("video", "document", "audio", "voice", "animation"):
        obj = getattr(message, attr, None)
        if obj and hasattr(obj, "file_size"):
            size_mb = (obj.file_size or 0) / (1024 * 1024)
            break
    if size_mb > max_mb:
        warn(f"Skip media {size_mb:.1f}MB (limit {max_mb}MB)")
        return None

    try:
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        fname = f"msg_{user_id}_{message.id}"
        path = await client.download_media(message, file_name=str(MEDIA_DIR / fname))
        if path:
            success(f"↓ {path}")
        return str(path) if path else None
    except Exception as e:
        warn(f"Gagal download msg {message.id}: {e}")
        return None


def media_label(message) -> str:
    if not message.media:
        return ""
    media_type = message.media.value if hasattr(message.media, "value") else str(message.media)
    return f"[{media_type}]"


# ══════════════════════════════════════════════════════════════════
# COMMON GROUPS + MESSAGES
# ══════════════════════════════════════════════════════════════════
async def read_common_groups(client: Client, user: User, msg_limit: int,
                             max_scan: int, download_media: bool,
                             max_mb: int, quiet: bool) -> list:
    section("Common Groups & Messages", "🌐")
    results = []

    try:
        common = await client.get_common_chats(user.id)
    except FloodWait as fw:
        warn(f"FloodWait {fw.value}s")
        await asyncio.sleep(fw.value)
        return results
    except Exception as e:
        error(f"Gagal ambil common chats: {e}")
        return results

    if not common:
        warn("Tidak ada grup bersama.")
        return results

    info(f"Total grup bersama: {len(common)}")

    for idx, chat in enumerate(common, 1):
        progress_bar(idx, len(common), prefix=f"Grup {idx}")

        chat_data = {
            "chat_id":  chat.id,
            "title":    chat.title,
            "type":     str(chat.type).split(".")[-1] if chat.type else None,
            "username": getattr(chat, "username", None),
            "members":  getattr(chat, "members_count", None),
            "description": (getattr(chat, "description", None) or "")[:150],
            "dc_id":    getattr(chat, "dc_id", None),
        }
        print()
        kv("Group",     chat_data["title"], RED)
        kv("Chat ID",   chat_data["chat_id"])
        kv("Type",      chat_data["type"])
        kv("Username",  f"@{chat_data['username']}" if chat_data["username"] else "None", "cyan")
        kv("Members",   chat_data["members"] if chat_data["members"] is not None else "N/A")
        kv("Desc",      chat_data["description"] or "None")

        messages = []
        count = 0
        scanned = 0

        try:
            async for message in client.get_chat_history(chat.id, limit=max_scan):
                scanned += 1
                if message.from_user and message.from_user.id == user.id:
                    ts = message.date.strftime("%Y-%m-%d %H:%M:%S")
                    text = message.text or media_label(message) or "[empty]"
                    entry = {
                        "chat_id": chat.id,
                        "chat_title": chat.title,
                        "date": ts,
                        "text": text,
                        "message_id": message.id,
                        "media_path": None,
                    }
                    if download_media and message.media:
                        entry["media_path"] = await try_download(
                            client, message, user.id, max_mb)
                    messages.append(entry)
                    if not quiet:
                        print(colored(f"    [{ts}] ", RED)
                              + colored(text[:120], "white"))
                    count += 1
                    if msg_limit > 0 and count >= msg_limit:
                        break
        except FloodWait as fw:
            warn(f"FloodWait {fw.value}s")
            await asyncio.sleep(fw.value)
        except (ChatAdminRequired, UserNotParticipant, ChannelPrivate, ChatForbidden):
            warn(f"Tidak ada akses history {chat_data['title']}")
        except Exception as e:
            error(f"Error di {chat_data['title']}: {e}")

        info(f"→ {count} pesan target ditemukan (scan {scanned} pesan)")
        results.append({"chat": chat_data, "messages": messages,
                        "scanned": scanned, "found": count})
    return results


# ══════════════════════════════════════════════════════════════════
# PRIVATE CHAT
# ══════════════════════════════════════════════════════════════════
async def read_private_chat(client: Client, user: User, msg_limit: int,
                            max_scan: int, download_media: bool,
                            max_mb: int, quiet: bool) -> list:
    section("Private Chat History", "💬")
    messages = []
    try:
        count = 0
        async for m in client.get_chat_history(user.id, limit=max_scan):
            # Baca SEMUA (dari target maupun dari kita) — biar lengkap
            ts = m.date.strftime("%Y-%m-%d %H:%M:%S")
            text = m.text or media_label(m) or "[empty]"
            sender = "TARGET" if (m.from_user and m.from_user.id == user.id) else "ME"
            entry = {
                "date": ts, "sender": sender, "text": text,
                "message_id": m.id, "media_path": None,
            }
            if download_media and m.media:
                entry["media_path"] = await try_download(client, m, user.id, max_mb)
            messages.append(entry)
            if not quiet:
                color = RED if sender == "TARGET" else "yellow"
                print(colored(f"    [{ts}] {sender:6}: ", color)
                      + colored(text[:120], "white"))
            count += 1
            if msg_limit > 0 and count >= msg_limit:
                break
        if count == 0:
            warn("Tidak ada private chat history.")
        else:
            info(f"→ {count} pesan dibaca dari private chat.")
    except Exception as e:
        warn(f"Tidak bisa akses private chat: {e}")
    return messages


# ══════════════════════════════════════════════════════════════════
# MENTION ANALYSIS
# ══════════════════════════════════════════════════════════════════
async def analyze_mentions(client: Client, user: User, groups: list,
                           limit_per_chat=1000) -> dict:
    section("Cross-Group Mention Analysis", "🎯")
    if not groups:
        warn("Tidak ada grup untuk dianalisis.")
        return {}

    mentioned_by = Counter()
    mentioned_users = Counter()
    replied_to = Counter()
    total = 0

    tu = (user.username or "").lower()
    tid = user.id
    tn = (user.first_name or "").lower()

    for g in groups:
        cid = g["chat"]["chat_id"]
        title = g["chat"]["title"]
        try:
            async for m in client.get_chat_history(cid, limit=limit_per_chat):
                total += 1
                text = (m.text or "").lower()
                hit = False
                if tu and f"@{tu}" in text:
                    hit = True
                if tn and len(tn) > 2 and tn in text:
                    hit = True
                if m.reply_to_message and m.reply_to_message.from_user \
                   and m.reply_to_message.from_user.id == tid:
                    hit = True
                    if m.from_user:
                        replied_to[m.from_user.id] += 1
                if hit and m.from_user and m.from_user.id != tid:
                    key = f"@{m.from_user.username}" if m.from_user.username \
                          else f"{m.from_user.first_name} ({m.from_user.id})"
                    mentioned_by[key] += 1
                if m.from_user and m.from_user.id == tid and text:
                    for mm in re.findall(r"@(\w{3,32})", text):
                        mentioned_users["@" + mm] += 1
        except FloodWait as fw:
            warn(f"FloodWait {fw.value}s")
            await asyncio.sleep(fw.value)
        except Exception as e:
            warn(f"Skip {title}: {e}")

    print(colored(f"\n   Pesan dianalisis: {total}", BRIGHT_RED, attrs=["bold"]))
    if mentioned_by:
        print(colored("\n   ▸ Top yang mention/reply target:", BRIGHT_RED, attrs=["bold"]))
        for k, c in mentioned_by.most_common(10):
            kv(k, c, RED)
    if mentioned_users:
        print(colored("\n   ▸ Top yang di-mention target:", BRIGHT_RED, attrs=["bold"]))
        for k, c in mentioned_users.most_common(10):
            kv(k, c, RED)
    if replied_to:
        print(colored("\n   ▸ Top yang di-reply target:", BRIGHT_RED, attrs=["bold"]))
        for k, c in replied_to.most_common(10):
            kv(f"User {k}", c, RED)

    return {
        "total_analyzed": total,
        "mentioned_by": mentioned_by.most_common(20),
        "mentioned_users": mentioned_users.most_common(20),
        "replied_to": replied_to.most_common(20),
    }


# ══════════════════════════════════════════════════════════════════
# ACTIVITY
# ══════════════════════════════════════════════════════════════════
def analyze_activity(all_msgs: list) -> dict:
    section("Activity Analysis", "📊")
    if not all_msgs:
        warn("Tidak ada data.")
        return {}

    hours = [0] * 24
    weekdays = [0] * 7
    for m in all_msgs:
        try:
            dt = datetime.strptime(m["date"], "%Y-%m-%d %H:%M:%S")
            hours[dt.hour] += 1
            weekdays[dt.weekday()] += 1
        except Exception:
            continue

    peak_h = hours.index(max(hours))
    peak_d = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][weekdays.index(max(weekdays))]
    est_tz = peak_h - 12

    print(colored("\n   Jam aktif (0-23):", BRIGHT_RED, attrs=["bold"]))
    for h in range(24):
        bar = "█" * int(hours[h] / max(1, max(hours)) * 20)
        print(colored(f"    {h:02d}:00 │{bar:<20}│ {hours[h]}", RED))

    print(colored("\n   Hari aktif:", BRIGHT_RED, attrs=["bold"]))
    for i, d in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
        bar = "█" * int(weekdays[i] / max(1, max(weekdays)) * 20)
        print(colored(f"    {d} │{bar:<20}│ {weekdays[i]}", RED))

    kv("Peak Hour", f"{peak_h:02d}:00", RED)
    kv("Peak Day",  peak_d, RED)
    kv("Est. TZ",   f"UTC{est_tz:+d} (kasar)", "yellow")
    return {"hourly": hours, "weekday": weekdays,
            "peak_hour": peak_h, "peak_day": peak_d, "est_tz": est_tz}


# ══════════════════════════════════════════════════════════════════
# SAVED / CONTACTS
# ══════════════════════════════════════════════════════════════════
async def read_saved(client: Client, limit=100) -> list:
    section("Saved Messages (Operator)", "📥")
    msgs = []
    try:
        async for m in client.get_chat_history("me", limit=limit):
            text = m.text or media_label(m) or "[empty]"
            msgs.append({"date": m.date.strftime("%Y-%m-%d %H:%M:%S"),
                         "text": text, "message_id": m.id})
            print(colored(f"    [{m.date.strftime('%Y-%m-%d %H:%M')}] {text[:100]}", RED))
        if not msgs:
            warn("Saved Messages kosong.")
    except Exception as e:
        error(f"Gagal: {e}")
    return msgs


async def read_contacts(client: Client, limit=500) -> list:
    section("Contacts (Operator)", "📇")
    contacts = []
    try:
        async for c in client.get_contacts(limit=limit):
            contacts.append({
                "id": c.id, "username": c.username,
                "first_name": c.first_name, "last_name": c.last_name,
                "phone": c.phone_number,
            })
        info(f"Total kontak: {len(contacts)}")
        for c in contacts[:15]:
            kv(c["first_name"] or "N/A",
               f"@{c['username'] or 'N/A'} | {c['phone'] or ''}")
        if len(contacts) > 15:
            warn(f"... dan {len(contacts) - 15} lainnya (lihat JSON).")
    except Exception as e:
        error(f"Gagal: {e}")
    return contacts


# ══════════════════════════════════════════════════════════════════
# EXPORT
# ══════════════════════════════════════════════════════════════════
def _safe(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s)


def export_json(payload: dict, target: str) -> str:
    REPORT_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"{_safe(target)}_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    success(f"JSON → {path}")
    return str(path)


def export_csv(payload: dict, target: str) -> str:
    REPORT_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"{_safe(target)}_{ts}.csv"

    rows = []
    for g in payload.get("groups", []):
        for m in g.get("messages", []):
            rows.append({
                "source": f"GROUP: {m['chat_title']}",
                "sender": "TARGET",
                "date": m["date"],
                "message_id": m["message_id"],
                "text": m["text"],
                "media": m.get("media_path") or "",
            })
    for m in payload.get("private_messages", []):
        rows.append({
            "source": "PRIVATE",
            "sender": m.get("sender", "TARGET"),
            "date": m["date"],
            "message_id": m["message_id"],
            "text": m["text"],
            "media": m.get("media_path") or "",
        })

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["source","sender","date","message_id","text","media"])
        w.writeheader()
        w.writerows(rows)
    success(f"CSV → {path}")
    return str(path)


def export_html(payload: dict, target: str) -> str:
    REPORT_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"{_safe(target)}_{ts}.html"

    u = payload.get("user", {})
    geo = payload.get("geo", {})
    act = payload.get("activity", {})
    s = payload.get("summary", {})

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Red Phantom — {target}</title>
<style>
 body{{background:#0a0a0a;color:#ffdddd;font-family:'Courier New',monospace;padding:20px;}}
 h1{{color:#ff2222;text-shadow:0 0 10px #ff0000;}}
 h2{{color:#ff4444;border-bottom:1px solid #ff2222;padding-bottom:4px;}}
 .kv{{display:grid;grid-template-columns:200px 1fr;gap:4px;margin:4px 0;}}
 .kv span:first-child{{color:#ff6666;font-weight:bold;}}
 .box{{background:#150000;border:1px solid #ff2222;padding:15px;border-radius:8px;margin:10px 0;}}
 .msg{{padding:3px 8px;border-left:2px solid #ff4444;margin:2px 0;}}
 .red{{color:#ff2222;}} .green{{color:#22ff88;}} .yellow{{color:#ffdd22;}}
</style></head><body>
<h1>🩸 RED PHANTOM OSINT REPORT</h1>
<p class="red">Generated: {payload.get('meta',{}).get('timestamp','')}</p>
<h2>🎯 Target</h2><div class="box">
<div class="kv"><span>Username</span><span>@{u.get('username') or 'None'}</span></div>
<div class="kv"><span>Name</span><span>{u.get('first_name','')} {u.get('last_name','') or ''}</span></div>
<div class="kv"><span>ID</span><span>{u.get('id')}</span></div>
<div class="kv"><span>Phone</span><span>{u.get('phone') or 'Hidden'}</span></div>
<div class="kv"><span>DC</span><span>{u.get('dc_id')}</span></div>
<div class="kv"><span>Status</span><span>{u.get('status') or 'None'}</span></div>
<div class="kv"><span>Bio</span><span>{u.get('bio') or 'None'}</span></div>
<div class="kv"><span>Premium</span><span>{u.get('is_premium')}</span></div>
</div>
<h2>🌍 Geo</h2><div class="box">
<div class="kv"><span>Coordinates</span><span>{(geo.get('coordinates') or {}).get('lat','-')}, {(geo.get('coordinates') or {}).get('lon','-')}</span></div>
<div class="kv"><span>Country</span><span>{geo.get('country') or '-'}</span></div>
<div class="kv"><span>City</span><span>{geo.get('city') or '-'}</span></div>
<div class="kv"><span>Maps</span><span>{geo.get('maps_link') or '-'}</span></div>
</div>
<h2>📊 Activity</h2><div class="box">
<div class="kv"><span>Peak Hour</span><span>{act.get('peak_hour')}:00</span></div>
<div class="kv"><span>Peak Day</span><span>{act.get('peak_day')}</span></div>
<div class="kv"><span>Est. TZ</span><span>UTC{act.get('est_tz',0):+d}</span></div>
</div>
<h2>📈 Summary</h2><div class="box">
<div class="kv"><span>Groups</span><span>{s.get('total_groups')}</span></div>
<div class="kv"><span>Messages</span><span>{s.get('total_msgs')}</span></div>
<div class="kv"><span>Private</span><span>{s.get('private_msgs')}</span></div>
</div>
<h2>💬 Messages</h2>
"""
    for g in payload.get("groups", []):
        html += f"<h3 class='red'>Group: {g['chat']['title']} ({g['chat']['chat_id']})</h3>"
        for m in g.get("messages", [])[:300]:
            media = f" <span class='yellow'>[MEDIA: {m.get('media_path')}]</span>" if m.get("media_path") else ""
            html += f"<div class='msg'><span class='red'>[{m['date']}]</span> {m['text'][:250]}{media}</div>"
    html += "</body></html>"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    success(f"HTML → {path}")
    return str(path)


# ══════════════════════════════════════════════════════════════════
# REAL-TIME MONITOR
# ══════════════════════════════════════════════════════════════════
def snap_user(u: User) -> dict:
    return {
        "username":   u.username,
        "first_name": u.first_name,
        "last_name":  u.last_name,
        "phone":      u.phone_number,
        "bio":        getattr(u, "bio", None),
        "status":     str(u.status) if u.status else None,
        "photo":      (u.photo.big_file_id if u.photo else None),
    }


async def monitor(client: Client, user: User, interval=60, iterations=0):
    section("🔴 Real-Time Monitor", "🔴")
    cprint("  Ctrl+C untuk stop", RED, attrs=["bold"])
    kv("Interval", f"{interval}s", RED)
    kv("Iterations", "∞" if iterations == 0 else iterations, RED)

    prev = snap_user(user)
    last_mid = 0
    try:
        async for m in client.get_chat_history(user.id, limit=1):
            last_mid = m.id
            break
    except Exception:
        pass

    i = 0
    try:
        while True:
            i += 1
            cprint(f"\n  ── Check #{i} · {datetime.now().strftime('%H:%M:%S')} ──",
                   RED, attrs=["bold"])

            try:
                fresh = await client.get_users(user.id)
            except FloodWait as fw:
                warn(f"FloodWait {fw.value}s")
                await asyncio.sleep(fw.value)
                continue
            except Exception as e:
                warn(f"Gagal refresh: {e}")
                await asyncio.sleep(interval)
                continue

            cur = snap_user(fresh)
            diffs = [(k, prev.get(k), cur.get(k)) for k in cur if prev.get(k) != cur.get(k)]

            if diffs:
                cprint(f"\n  ⚠  {len(diffs)} PERUBAHAN!", "yellow", attrs=["bold"])
                for k, o, n in diffs:
                    print(colored(f"    ▸ {k}: ", BRIGHT_RED)
                          + colored(f"{str(o)[:40]} ", "white")
                          + colored("→", "yellow")
                          + colored(f" {str(n)[:40]}", "green"))
                track_username(fresh)
                REPORT_DIR.mkdir(exist_ok=True)
                changes_file = REPORT_DIR / f"changes_{user.id}.json"
                logs = []
                if changes_file.exists():
                    try:
                        logs = json.load(open(changes_file))
                    except Exception:
                        logs = []
                logs.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "changes": [{"field": k, "old": o, "new": n} for k, o, n in diffs],
                })
                with open(changes_file, "w") as f:
                    json.dump(logs, f, indent=2, default=str, ensure_ascii=False)
            else:
                info("Tidak ada perubahan profil.")

            # Cek pesan baru masuk
            new_msgs = []
            try:
                async for m in client.get_chat_history(user.id, limit=20):
                    if m.id <= last_mid:
                        break
                    if m.from_user and m.from_user.id == user.id:
                        new_msgs.append({
                            "date": m.date.strftime("%Y-%m-%d %H:%M:%S"),
                            "text": m.text or media_label(m) or "[media]",
                            "id": m.id,
                        })
                if new_msgs:
                    last_mid = max(x["id"] for x in new_msgs)
                    cprint(f"\n  💬 {len(new_msgs)} PESAN BARU:", "yellow", attrs=["bold"])
                    for x in reversed(new_msgs):
                        print(colored(f"    [{x['date']}] ", RED)
                              + colored(x["text"][:120], "white"))
            except Exception as e:
                warn(f"Gagal cek pesan: {e}")

            prev = cur
            if iterations > 0 and i >= iterations:
                cprint(f"\n  ✔ Monitor selesai ({i} iterasi).", "green")
                break
            cprint(f"\n  ⏳ Next in {interval}s...", BRIGHT_RED)
            await asyncio.sleep(interval)
    except KeyboardInterrupt:
        cprint("\n  [!] Monitor dihentikan user.", "yellow")


# ══════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════
async def run(client: Client):
    # Resolve target manual
    user = await resolve_target(client)
    if not user:
        warn("Target tidak resolved, keluar.")
        return

    # Menu pilihan
    opts = main_menu()
    if opts is None:
        info("Keluar.")
        return

    # Parameter tambahan (manual)
    section("Parameter Scrape (Manual)", "⚙")
    msg_limit = ask_int("Limit pesan per chat (0=unlimited)", default=100, min_val=0)
    max_scan  = ask_int("Max pesan di-scan per chat", default=5000, min_val=1)
    download  = ask_yes_no("Download media (foto/video)?", "n")
    max_mb    = ask_int("Max ukuran media (MB)", default=20, min_val=1) if download else 20

    # Jalankan modul sesuai pilihan
    payload = {
        "meta": {"tool": "Red Phantom", "version": "4.0",
                 "timestamp": datetime.now(timezone.utc).isoformat(),
                 "target": user.username or str(user.id)},
    }

    me = await client.get_me()
    section("Operator (Anda)", "🔐")
    kv("Username", f"@{me.username}" if me.username else "None")
    kv("Name",     f"{me.first_name or ''} {me.last_name or ''}".strip())
    kv("ID",       me.id)
    kv("Phone",    me.phone_number or "None")
    payload["operator"] = {"id": me.id, "username": me.username, "phone": me.phone_number}

    groups = []
    private_msgs = []

    if opts.get("profile"):
        payload["user"] = await read_profile(client, user)
        payload["username_history"] = track_username(user)
        payload["geo"] = geo_from_bio(payload["user"].get("bio") or "")
        show_geo(payload["geo"])

    if opts.get("photos"):
        payload["photos"] = await read_profile_photos(client, user, download=download)

    if opts.get("groups"):
        groups = await read_common_groups(client, user, msg_limit, max_scan,
                                         download, max_mb, quiet=False)
        payload["groups"] = groups

    if opts.get("private"):
        private_msgs = await read_private_chat(client, user, msg_limit, max_scan,
                                              download, max_mb, quiet=False)
        payload["private_messages"] = private_msgs

    if opts.get("mentions"):
        payload["mentions"] = await analyze_mentions(client, user, groups)

    if opts.get("activity"):
        all_msgs = []
        for g in groups:
            all_msgs.extend(g["messages"])
        all_msgs.extend(private_msgs)
        payload["activity"] = analyze_activity(all_msgs)

    if opts.get("saved"):
        payload["saved_messages"] = await read_saved(client)

    if opts.get("contacts"):
        payload["contacts"] = await read_contacts(client)

    if opts.get("monitor"):
        await monitor(client, user)
        return

    # Summary
    total_msgs = sum(len(g["messages"]) for g in groups) + len(private_msgs)
    payload["summary"] = {
        "total_groups": len(groups),
        "total_msgs": total_msgs,
        "private_msgs": len(private_msgs),
        "photos": len(payload.get("photos", [])),
    }
    section("Summary", "✅")
    kv("Groups",  len(groups), RED)
    kv("Messages", total_msgs, RED)
    kv("Private",  len(private_msgs), RED)
    kv("Photos",   len(payload.get("photos", [])), RED)

    # Export
    section("Export", "💾")
    tgt = user.username or str(user.id)
    export_json(payload, tgt)
    export_csv(payload, tgt)
    export_html(payload, tgt)

    cprint("\n  ══ SELESAI ══", RED, attrs=["bold"])
    cprint("  Red Phantom · Stay sharp, stay red.\n", BRIGHT_RED)


# ══════════════════════════════════════════════════════════════════
# ENTRY
# ══════════════════════════════════════════════════════════════════
async def main():
    banner()
    config = get_config()
    app = Client(config["session_name"],
                 api_id=int(config["api_id"]),
                 api_hash=config["api_hash"])
    async with app:
        await run(app)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        cprint("\n\n  [!] Dibatalkan user.\n", RED, attrs=["bold"])
        sys.exit(0)
    except AuthKeyUnregistered:
        cprint("\n  [FATAL] Session invalid — hapus *.session, login ulang.\n", RED)
        sys.exit(1)
    except Exception as e:
        cprint(f"\n  [FATAL] {e}\n", RED, attrs=["bold"])
        sys.exit(1)
