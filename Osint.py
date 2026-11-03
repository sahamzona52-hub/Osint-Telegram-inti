#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║   RED PHANTOM OSINT — PRODUCTION READY                               ║
║   Tested on Pyrogram 2.0.106 · Python 3.9+                          ║
║   Powered by Yusiqo · For AUTHORIZED use only                        ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import os
import sys
import re
import json
import csv
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

# ── Third party ────────────────────────────────────────────────────
try:
    from pyrogram import Client, filters
    from pyrogram.errors import (
        PeerIdInvalid, UsernameInvalid, UsernameNotOccupied,
        FloodWait, ChatAdminRequired, UserNotParticipant,
        ChannelPrivate, ChatForbidden, AuthKeyUnregistered,
        MessageTooLong, MessageNotModified,
    )
    from pyrogram.types import User, Message
    from pyfiglet import figlet_format
    from termcolor import colored
except ImportError as e:
    print(f"[FATAL] Missing dependency: {e}")
    print("Install: pip install pyrogram==2.0.106 TgCrypto==1.2.5 "
          "pyfiglet==0.8.post1 termcolor==2.4.0")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════
# ⚙  KONFIGURASI
# ══════════════════════════════════════════════════════════════════
BOT_CONFIG = {
    "bot_token": "8831458505:AAFv8SB4O6eAwSdISxfEQ9YXZwrR34ZN3C4",
    "admin_ids": [8466466096],
    "notify_realtime": True,
    "send_files": True,
    "scan_timeout_sec": 300,
    "default_msg_limit": 100,
    "default_max_scan": 3000,
    "default_max_mb": 20,
}

CONFIG_FILE = "config.json"
REPORT_DIR  = Path("reports")
MEDIA_DIR   = REPORT_DIR / "media"
HISTORY_DIR = Path("history")
BOT_STATE   = Path("bot_state.json")

RED        = "red"
BRIGHT_RED = "light_red"
GREEN      = "green"
YELLOW     = "yellow"


# ══════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════
def cprint(text, color=BRIGHT_RED, attrs=None):
    try:
        print(colored(text, color, attrs=attrs))
    except Exception:
        print(text)


def banner():
    try:
        os.system("clear" if os.name == "posix" else "cls")
    except Exception:
        pass
    try:
        art = figlet_format("RED PHANTOM", font="slant")
        cprint(art, RED, attrs=["bold"])
    except Exception:
        cprint("=== RED PHANTOM ===", RED, attrs=["bold"])
    line = "═" * 64
    cprint(f"  {line}", RED)
    cprint("   ⚡  TELEGRAM OSINT · PRODUCTION READY  ⚡", RED, attrs=["bold"])
    cprint(f"  {line}", RED)
    cprint("   ▸ Tool   : Red Phantom Production", BRIGHT_RED)
    cprint("   ▸ Author : Yusiqo", BRIGHT_RED)
    cprint(f"  {line}\n", RED)


def section(title, icon="◆", quiet=False):
    if quiet:
        return
    line = "─" * 62
    cprint(f"\n┌{line}┐", RED)
    cprint(f"│ {icon} {title.upper():<59}│", RED, attrs=["bold"])
    cprint(f"└{line}┘", RED)


def kv(label, value, value_color="white", quiet=False):
    if quiet:
        return
    left  = colored(f"    ▹ {label:<18}: ", BRIGHT_RED, attrs=["bold"])
    right = colored(str(value), value_color)
    print(f"{left}{right}")


def status(tag, message, color=BRIGHT_RED):
    print(colored(f"  [{tag}] ", color, attrs=["bold"]) + colored(message, "white"))


def success(msg): status("✔", msg, GREEN)
def warn(msg):    status("!", msg, YELLOW)
def error(msg):   status("✘", msg, RED)
def info(msg):    status("›", msg, BRIGHT_RED)


def progress_bar(i, total, prefix="", length=30, quiet=False):
    if quiet:
        return
    filled = int(length * i // total) if total else length
    bar = "█" * filled + "░" * (length - filled)
    print(colored(f"\r  {prefix} |{bar}| {i}/{total}", RED), end="", flush=True)
    if i >= total:
        print()


def ask(prompt, default=None, allow_empty=False):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        try:
            raw = input(colored(f"  ▸ {prompt}{suffix}: ", BRIGHT_RED)).strip()
        except (EOFError, KeyboardInterrupt):
            return default if default is not None else ""
        if not raw:
            if default is not None:
                return default
            if allow_empty:
                return ""
            warn("Input tidak boleh kosong.")
            continue
        return raw


def ask_yes_no(prompt, default="n"):
    raw = ask(prompt + " (y/n)", default=default)
    return str(raw).strip().lower() in ("y", "yes", "1", "true")


def ask_int(prompt, default=None, min_val=0):
    while True:
        raw = ask(prompt, default=str(default) if default is not None else None)
        if not raw:
            return default if default is not None else min_val
        try:
            v = int(raw)
            if v < min_val:
                warn(f"Minimal {min_val}")
                continue
            return v
        except ValueError:
            warn("Harus angka.")


# ══════════════════════════════════════════════════════════════════
# MARKDOWN HELPERS
# ══════════════════════════════════════════════════════════════════
def md_escape(s, max_len=200) -> str:
    if s is None:
        return "None"
    s = str(s)
    for ch in ["_", "*", "[", "]", "`", "(", ")", "~", ">", "#", "+", "-", "=", "|", "{", "}"]:
        s = s.replace(ch, "\\" + ch)
    if len(s) > max_len:
        s = s[:max_len] + "…"
    return s


# ══════════════════════════════════════════════════════════════════
# BOT NOTIFIER
# ══════════════════════════════════════════════════════════════════
class BotNotifier:
    def __init__(self, bot_client: Client, admin_ids: list):
        self.bot = bot_client
        self.admin_ids = admin_ids

    def _chunk(self, text: str, size: int = 3500) -> list:
        chunks, cur = [], ""
        for line in text.split("\n"):
            if len(cur) + len(line) + 1 > size:
                if cur:
                    chunks.append(cur)
                cur = line
            else:
                cur += ("\n" if cur else "") + line
        if cur:
            chunks.append(cur)
        return chunks or [text[:size]]

    async def send_text(self, text: str, markdown=True):
        if not text:
            return
        for aid in self.admin_ids:
            for chunk in self._chunk(text):
                try:
                    await self.bot.send_message(
                        aid, chunk,
                        parse_mode="markdown" if markdown else None,
                        disable_web_page_preview=True,
                    )
                except (MessageTooLong, MessageNotModified):
                    try:
                        await self.bot.send_message(aid, chunk[:4000])
                    except Exception:
                        pass
                except FloodWait as fw:
                    try:
                        await asyncio.sleep(fw.value + 1)
                        await self.bot.send_message(aid, chunk)
                    except Exception:
                        pass
                except Exception:
                    try:
                        plain = re.sub(r"[*_`\[\]]", "", chunk)
                        await self.bot.send_message(aid, plain)
                    except Exception:
                        pass

    async def send_file(self, filepath: str, caption=""):
        if not filepath or not Path(filepath).exists():
            return
        for aid in self.admin_ids:
            try:
                await self.bot.send_document(aid, filepath, caption=caption)
            except FloodWait as fw:
                try:
                    await asyncio.sleep(fw.value + 1)
                    await self.bot.send_document(aid, filepath, caption=caption)
                except Exception:
                    pass
            except Exception as e:
                warn(f"Bot file error: {type(e).__name__}")

    async def send_profile_summary(self, u: dict, geo: dict, summary: dict):
        md = f"""🩸 **RED PHANTOM — SCAN RESULT**

👤 **Target**
• Username: `@{md_escape(u.get('username') or 'None', 40)}`
• Name: **{md_escape(u.get('first_name') or '', 50)} {md_escape(u.get('last_name') or '', 50)}**
• ID: `{u.get('id')}`
• Phone: `{md_escape(u.get('phone') or 'Hidden', 20)}`
• DC: `{u.get('dc_id')}`
• Status: `{md_escape(u.get('status') or 'None', 40)}`

📝 **Bio**
`{md_escape(u.get('bio') or 'None', 200)}`

🏷 **Flags**
Bot:`{u.get('is_bot')}` · Verified:`{u.get('is_verified')}` · Premium:`{u.get('is_premium')}`
Scam:`{u.get('is_scam')}` · Fake:`{u.get('is_fake')}`

🌍 **Geo**
Country: `{geo.get('country') or '-'}`
City: `{geo.get('city') or '-'}`
Maps: `{geo.get('maps_link') or '-'}`

📊 **Summary**
Groups: `{summary.get('total_groups', 0)}` · Messages: `{summary.get('total_msgs', 0)}`
Private: `{summary.get('private_msgs', 0)}` · Photos: `{summary.get('photos', 0)}`
"""
        await self.send_text(md)

    async def send_change_alert(self, user: User, changes: list):
        md = f"🚨 **PROFILE CHANGE**\n\n`@{md_escape(user.username or 'None', 40)}` ({user.id})\n\n"
        for ch in changes:
            md += f"▸ **{ch['field']}**\n"
            md += f"  Old: `{md_escape(ch['old'], 80)}`\n"
            md += f"  New: `{md_escape(ch['new'], 80)}`\n\n"
        md += f"🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        await self.send_text(md)

    async def send_new_message(self, user: User, msg: dict):
        md = f"💬 **NEW MSG** `@{md_escape(user.username or user.id, 40)}`\n\n"
        md += f"🕐 `{msg['date']}`\n📝 {md_escape(msg['text'][:500], 500)}"
        await self.send_text(md)


# ══════════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════════
def load_bot_state() -> dict:
    if BOT_STATE.exists():
        try:
            return json.load(open(BOT_STATE))
        except Exception:
            return {}
    return {}


def save_bot_state(state: dict):
    try:
        with open(BOT_STATE, "w") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
# MONITOR
# ══════════════════════════════════════════════════════════════════
def snap_user(u: User) -> dict:
    return {
        "username": u.username, "first_name": u.first_name,
        "last_name": u.last_name, "phone": u.phone_number,
        "bio": getattr(u, "bio", None),
        "status": str(u.status) if u.status else None,
        "photo": (u.photo.big_file_id if u.photo else None),
    }


async def monitor_with_bot(client: Client, user: User,
                           notifier: BotNotifier, interval=60):
    info(f"Monitor start: @{user.username or user.id}")
    prev = snap_user(user)
    last_mid = 0
    try:
        async for m in client.get_chat_history(user.id, limit=1):
            last_mid = m.id
            break
    except Exception:
        pass

    err_count = 0
    while True:
        state = load_bot_state()
        if str(user.id) not in state.get("monitors", {}):
            info(f"Monitor stop: @{user.username or user.id}")
            return
        if err_count >= 10:
            warn("Monitor auto-stop: too many errors")
            state["monitors"].pop(str(user.id), None)
            save_bot_state(state)
            return

        try:
            fresh = await client.get_users(user.id)
            err_count = 0
        except FloodWait as fw:
            await asyncio.sleep(fw.value + 1)
            continue
        except Exception:
            err_count += 1
            await asyncio.sleep(interval)
            continue

        cur = snap_user(fresh)
        diffs = [(k, prev.get(k), cur.get(k)) for k in cur if prev.get(k) != cur.get(k)]

        if diffs:
            info(f"⚠ {len(diffs)} perubahan @{fresh.username or fresh.id}")
            changes_list = [{"field": k, "old": o, "new": n} for k, o, n in diffs]
            try:
                await notifier.send_change_alert(fresh, changes_list)
            except Exception:
                pass
            try:
                track_username(fresh, quiet=True)
            except Exception:
                pass

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
                for x in reversed(new_msgs):
                    try:
                        await notifier.send_new_message(fresh, x)
                    except Exception:
                        pass
        except Exception:
            pass

        prev = cur
        await asyncio.sleep(interval)


# ══════════════════════════════════════════════════════════════════
# CORE SCRAPE
# ══════════════════════════════════════════════════════════════════
def media_label(message) -> str:
    if not message.media:
        return ""
    try:
        return f"[{message.media.value}]"
    except Exception:
        return "[media]"


async def try_download(client: Client, message, user_id: int,
                       max_mb=20, quiet=True) -> str | None:
    if not message.media:
        return None
    size_mb = 0
    for attr in ("video", "document", "audio", "voice", "animation"):
        obj = getattr(message, attr, None)
        if obj and hasattr(obj, "file_size"):
            size_mb = (obj.file_size or 0) / (1024 * 1024)
            break
    if size_mb > max_mb:
        return None
    try:
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        path = await client.download_media(
            message, file_name=str(MEDIA_DIR / f"msg_{user_id}_{message.id}"))
        return str(path) if path else None
    except Exception:
        return None


async def read_profile(client: Client, user: User, quiet=False) -> dict:
    section("Full Profile", "🎯", quiet=quiet)
    try:
        user = await client.get_users(user.id)
    except Exception:
        pass

    data = {
        "id": user.id, "username": user.username,
        "first_name": user.first_name, "last_name": user.last_name,
        "phone": user.phone_number, "dc_id": user.dc_id,
        "language": user.language_code,
        "status": str(user.status) if user.status else None,
        "bio": getattr(user, "bio", None),
        "is_bot": user.is_bot, "is_verified": user.is_verified,
        "is_premium": getattr(user, "is_premium", False),
        "is_restricted": user.is_restricted,
        "is_scam": user.is_scam, "is_fake": user.is_fake,
        "is_support": getattr(user, "is_support", False),
        "photo": None,
    }
    if user.photo:
        data["photo"] = {
            "small_file_id": user.photo.small_file_id,
            "big_file_id":   user.photo.big_file_id,
            "dc_id":         user.photo.dc_id,
        }

    if not quiet:
        for k, v, col in [
            ("ID", data["id"], RED),
            ("Username", f"@{data['username']}" if data["username"] else "None", RED),
            ("First Name", data["first_name"] or "None", "white"),
            ("Last Name", data["last_name"] or "None", "white"),
            ("Phone", data["phone"] or "Hidden", YELLOW),
            ("DC ID", data["dc_id"], "white"),
            ("Language", data["language"] or "None", "white"),
            ("Status", data["status"] or "None", "white"),
            ("Bio", data["bio"] or "None", "cyan"),
            ("Bot", "Yes" if data["is_bot"] else "No", "white"),
            ("Verified", "Yes" if data["is_verified"] else "No", "cyan"),
            ("Premium", "Yes" if data["is_premium"] else "No", "cyan"),
            ("Restricted", "Yes" if data["is_restricted"] else "No", "white"),
            ("Scam", "Yes" if data["is_scam"] else "No", RED if data["is_scam"] else "white"),
            ("Fake", "Yes" if data["is_fake"] else "No", RED if data["is_fake"] else "white"),
            ("Has Photo", "Yes" if data["photo"] else "No", "white"),
        ]:
            kv(k, v, col)
    return data


async def read_profile_photos(client: Client, user: User, limit=10,
                              download=False, quiet=True) -> list:
    section("Profile Photos", "📸", quiet=quiet)
    photos = []
    try:
        async for photo in client.get_chat_photos(user.id, limit=limit):
            entry = {"date": str(photo.date), "file_id": photo.file_id,
                     "dc_id": photo.dc_id, "local_path": None}
            if download:
                try:
                    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                    fname = f"profile_{user.id}_{photo.date.strftime('%Y%m%d_%H%M%S')}.jpg"
                    path = await client.download_media(
                        photo.file_id, file_name=str(MEDIA_DIR / fname))
                    if path:
                        entry["local_path"] = str(path)
                except Exception:
                    pass
            photos.append(entry)
    except Exception:
        pass
    return photos


COUNTRY_HINTS = {
    "indonesia": "Indonesia", "jakarta": "Indonesia", "bandung": "Indonesia",
    "surabaya": "Indonesia", "bali": "Indonesia", "medan": "Indonesia",
    "yogyakarta": "Indonesia", "semarang": "Indonesia", "makassar": "Indonesia",
    "singapore": "Singapore", "malaysia": "Malaysia", "thailand": "Thailand",
    "bangkok": "Thailand", "vietnam": "Vietnam", "philippines": "Philippines",
    "japan": "Japan", "tokyo": "Japan", "korea": "South Korea", "seoul": "South Korea",
    "china": "China", "beijing": "China", "india": "India", "usa": "USA",
    "new york": "USA", "uk": "UK", "london": "UK", "germany": "Germany",
    "france": "France", "paris": "France", "spain": "Spain", "italy": "Italy",
    "russia": "Russia", "australia": "Australia", "canada": "Canada",
    "brazil": "Brazil", "mexico": "Mexico", "turkey": "Turkey", "dubai": "UAE",
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
        bio)
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


def show_geo(geo: dict, quiet=False):
    section("Geolocation", "🌍", quiet=quiet)
    if not any([geo["coordinates"], geo["maps_link"], geo["country"], geo["city"]]):
        return
    if geo["coordinates"]:
        kv("Coordinates", f"{geo['coordinates']['lat']}, {geo['coordinates']['lon']}", RED, quiet)
    if geo["maps_link"]:
        kv("Maps Link", geo["maps_link"], "cyan", quiet)
    if geo["country"]:
        kv("Country", geo["country"], RED, quiet)
    if geo["city"]:
        kv("City", geo["city"], quiet=quiet)
    if geo["hits"]:
        kv("Hints", ", ".join(geo["hits"]), YELLOW, quiet)


def track_username(user: User, quiet=False) -> dict:
    section("Username History", "🔗", quiet=quiet)
    try:
        HISTORY_DIR.mkdir(exist_ok=True)
        file = HISTORY_DIR / f"user_{user.id}.json"
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "username": user.username, "first_name": user.first_name,
            "last_name": user.last_name, "phone": user.phone_number,
            "bio": getattr(user, "bio", None),
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
        try:
            with open(file, "w") as f:
                json.dump(history, f, indent=2, ensure_ascii=False, default=str)
        except Exception:
            pass
        if not quiet:
            kv("Current", f"@{user.username}" if user.username else "None", RED)
            kv("Snapshots", len(history))
            if prev:
                kv("Previous", ", ".join(f"@{u}" for u in set(prev)))
        return {"current": user.username, "history": history, "changed": changed}
    except Exception:
        return {"current": user.username, "history": [], "changed": False}


async def read_common_groups(client: Client, user: User, msg_limit: int,
                             max_scan: int, download_media: bool,
                             max_mb: int, quiet=True) -> list:
    section("Common Groups", "🌐", quiet=quiet)
    results = []
    try:
        common = await client.get_common_chats(user.id)
    except FloodWait as fw:
        await asyncio.sleep(fw.value + 1)
        return results
    except Exception:
        return results

    if not common:
        return results

    for idx, chat in enumerate(common, 1):
        progress_bar(idx, len(common), prefix=f"Grup {idx}", quiet=quiet)
        chat_data = {
            "chat_id": chat.id, "title": chat.title,
            "type": str(chat.type).split(".")[-1] if chat.type else None,
            "username": getattr(chat, "username", None),
            "members": getattr(chat, "members_count", None),
            "description": (getattr(chat, "description", None) or "")[:150],
            "dc_id": getattr(chat, "dc_id", None),
        }
        messages, count, scanned = [], 0, 0
        try:
            async for message in client.get_chat_history(chat.id, limit=max_scan):
                scanned += 1
                if message.from_user and message.from_user.id == user.id:
                    ts = message.date.strftime("%Y-%m-%d %H:%M:%S")
                    text = message.text or media_label(message) or "[empty]"
                    entry = {"chat_id": chat.id, "chat_title": chat.title,
                             "date": ts, "text": text, "message_id": message.id,
                             "media_path": None}
                    if download_media and message.media:
                        entry["media_path"] = await try_download(
                            client, message, user.id, max_mb, quiet)
                    messages.append(entry)
                    count += 1
                    if msg_limit > 0 and count >= msg_limit:
                        break
        except FloodWait as fw:
            await asyncio.sleep(fw.value + 1)
        except (ChatAdminRequired, UserNotParticipant, ChannelPrivate, ChatForbidden):
            pass
        except Exception:
            pass
        results.append({"chat": chat_data, "messages": messages,
                        "scanned": scanned, "found": count})
    return results


async def read_private_chat(client: Client, user: User, msg_limit: int,
                            max_scan: int, download_media: bool,
                            max_mb: int, quiet=True) -> list:
    section("Private Chat", "💬", quiet=quiet)
    messages = []
    try:
        count = 0
        async for m in client.get_chat_history(user.id, limit=max_scan):
            ts = m.date.strftime("%Y-%m-%d %H:%M:%S")
            text = m.text or media_label(m) or "[empty]"
            sender = "TARGET" if (m.from_user and m.from_user.id == user.id) else "ME"
            entry = {"date": ts, "sender": sender, "text": text,
                     "message_id": m.id, "media_path": None}
            if download_media and m.media:
                entry["media_path"] = await try_download(
                    client, m, user.id, max_mb, quiet)
            messages.append(entry)
            count += 1
            if msg_limit > 0 and count >= msg_limit:
                break
    except Exception:
        pass
    return messages


async def analyze_mentions(client: Client, user: User, groups: list,
                           limit_per_chat=1000, quiet=True) -> dict:
    section("Mention Analysis", "🎯", quiet=quiet)
    if not groups:
        return {}
    mentioned_by, mentioned_users, replied_to = Counter(), Counter(), Counter()
    total = 0
    tu = (user.username or "").lower()
    tid = user.id
    tn = (user.first_name or "").lower()

    for g in groups:
        cid = g["chat"]["chat_id"]
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
            await asyncio.sleep(fw.value + 1)
        except Exception:
            pass
    return {"total_analyzed": total,
            "mentioned_by": mentioned_by.most_common(20),
            "mentioned_users": mentioned_users.most_common(20),
            "replied_to": replied_to.most_common(20)}


def analyze_activity(all_msgs: list, quiet=False) -> dict:
    section("Activity", "📊", quiet=quiet)
    if not all_msgs:
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
    if not quiet:
        for h in range(24):
            bar = "█" * int(hours[h] / max(1, max(hours)) * 20)
            print(colored(f"    {h:02d}:00 │{bar:<20}│ {hours[h]}", RED))
        kv("Peak Hour", f"{peak_h:02d}:00", RED)
        kv("Peak Day", peak_d, RED)
        kv("Est. TZ", f"UTC{est_tz:+d}", YELLOW)
    return {"hourly": hours, "weekday": weekdays,
            "peak_hour": peak_h, "peak_day": peak_d, "est_tz": est_tz}


async def read_saved(client: Client, limit=100, quiet=True) -> list:
    section("Saved Messages", "📥", quiet=quiet)
    msgs = []
    try:
        async for m in client.get_chat_history("me", limit=limit):
            msgs.append({"date": m.date.strftime("%Y-%m-%d %H:%M:%S"),
                         "text": m.text or media_label(m) or "[empty]",
                         "message_id": m.id})
    except Exception:
        pass
    return msgs


async def read_contacts(client: Client, limit=500, quiet=True) -> list:
    section("Contacts", "📇", quiet=quiet)
    contacts = []
    try:
        async for c in client.get_contacts(limit=limit):
            contacts.append({"id": c.id, "username": c.username,
                             "first_name": c.first_name, "last_name": c.last_name,
                             "phone": c.phone_number})
    except Exception:
        pass
    return contacts


# ══════════════════════════════════════════════════════════════════
# EXPORTS
# ══════════════════════════════════════════════════════════════════
def _safe(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in str(s))


def export_json(payload: dict, target: str, quiet=False) -> str:
    try:
        REPORT_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = REPORT_DIR / f"{_safe(target)}_{ts}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        if not quiet:
            success(f"JSON → {path}")
        return str(path)
    except Exception:
        return ""


def export_csv(payload: dict, target: str, quiet=False) -> str:
    try:
        REPORT_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = REPORT_DIR / f"{_safe(target)}_{ts}.csv"
        rows = []
        for g in payload.get("groups", []):
            for m in g.get("messages", []):
                rows.append({"source": f"GROUP: {m['chat_title']}", "sender": "TARGET",
                             "date": m["date"], "message_id": m["message_id"],
                             "text": m["text"], "media": m.get("media_path") or ""})
        for m in payload.get("private_messages", []):
            rows.append({"source": "PRIVATE", "sender": m.get("sender", "TARGET"),
                         "date": m["date"], "message_id": m["message_id"],
                         "text": m["text"], "media": m.get("media_path") or ""})
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["source","sender","date","message_id","text","media"])
            w.writeheader()
            w.writerows(rows)
        if not quiet:
            success(f"CSV → {path}")
        return str(path)
    except Exception:
        return ""


def export_html(payload: dict, target: str, quiet=False) -> str:
    try:
        REPORT_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = REPORT_DIR / f"{_safe(target)}_{ts}.html"
        u = payload.get("user", {})
        geo = payload.get("geo", {})
        s = payload.get("summary", {})
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Red Phantom — {target}</title>
<style>body{{background:#0a0a0a;color:#ffdddd;font-family:monospace;padding:20px;}}
h1{{color:#ff2222;}}h2{{color:#ff4444;border-bottom:1px solid #ff2222;}}
.kv{{display:grid;grid-template-columns:200px 1fr;margin:4px 0;}}
.kv span:first-child{{color:#ff6666;font-weight:bold;}}
.box{{background:#150000;border:1px solid #ff2222;padding:15px;border-radius:8px;margin:10px 0;}}
.msg{{padding:3px 8px;border-left:2px solid #ff4444;margin:2px 0;}}</style>
</head><body>
<h1>🩸 RED PHANTOM REPORT</h1>
<p style="color:#ff2222">Generated: {payload.get('meta',{}).get('timestamp','')}</p>
<h2>🎯 Target</h2><div class="box">
<div class="kv"><span>Username</span><span>@{u.get('username') or 'None'}</span></div>
<div class="kv"><span>Name</span><span>{u.get('first_name','')} {u.get('last_name','') or ''}</span></div>
<div class="kv"><span>ID</span><span>{u.get('id')}</span></div>
<div class="kv"><span>Phone</span><span>{u.get('phone') or 'Hidden'}</span></div>
<div class="kv"><span>Bio</span><span>{u.get('bio') or 'None'}</span></div>
</div>
<h2>🌍 Geo</h2><div class="box">
<div class="kv"><span>Country</span><span>{geo.get('country') or '-'}</span></div>
<div class="kv"><span>City</span><span>{geo.get('city') or '-'}</span></div>
<div class="kv"><span>Maps</span><span>{geo.get('maps_link') or '-'}</span></div>
</div>
<h2>📈 Summary</h2><div class="box">
<div class="kv"><span>Groups</span><span>{s.get('total_groups')}</span></div>
<div class="kv"><span>Messages</span><span>{s.get('total_msgs')}</span></div>
<div class="kv"><span>Private</span><span>{s.get('private_msgs')}</span></div>
</div>
<h2>💬 Messages</h2>"""
        for g in payload.get("groups", []):
            html += f"<h3 style='color:#ff2222'>Group: {g['chat']['title']}</h3>"
            for m in g.get("messages", [])[:300]:
                html += f"<div class='msg'><span style='color:#ff2222'>[{m['date']}]</span> {m['text'][:250]}</div>"
        html += "</body></html>"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        if not quiet:
            success(f"HTML → {path}")
        return str(path)
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════
# SCAN ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════
async def scan_and_export(client: Client, user: User, msg_limit: int,
                          notifier: BotNotifier = None,
                          max_scan: int = 3000,
                          download: bool = False,
                          max_mb: int = 20,
                          quiet: bool = True) -> dict:
    try:
        return await asyncio.wait_for(
            _scan_inner(client, user, msg_limit, notifier, max_scan,
                        download, max_mb, quiet),
            timeout=BOT_CONFIG.get("scan_timeout_sec", 300),
        )
    except asyncio.TimeoutError:
        error("Scan timeout (5 menit)")
        if notifier:
            try:
                await notifier.send_text("⏰ Scan timeout (5 menit).")
            except Exception:
                pass
        return {}
    except Exception as e:
        error(f"Scan error: {e}")
        if notifier:
            try:
                await notifier.send_text(f"❌ Scan error: `{md_escape(str(e), 200)}`")
            except Exception:
                pass
        return {}


async def _scan_inner(client, user, msg_limit, notifier, max_scan,
                      download, max_mb, quiet):
    user_data = await read_profile(client, user, quiet=quiet)
    history = track_username(user, quiet=quiet)
    geo = geo_from_bio(user_data.get("bio") or "")
    show_geo(geo, quiet=quiet)

    photos = await read_profile_photos(client, user, limit=10,
                                       download=download, quiet=quiet)

    # Parallel: groups + private
    groups_task = read_common_groups(client, user, msg_limit, max_scan,
                                     download, max_mb, quiet=quiet)
    private_task = read_private_chat(client, user, msg_limit, max_scan,
                                     download, max_mb, quiet=quiet)
    try:
        groups, private_msgs = await asyncio.gather(groups_task, private_task)
    except Exception as e:
        error(f"Gather error: {e}")
        groups, private_msgs = [], []

    mentions = await analyze_mentions(client, user, groups, quiet=quiet)
    all_msgs = []
    for g in groups:
        all_msgs.extend(g["messages"])
    all_msgs.extend(private_msgs)
    activity = analyze_activity(all_msgs, quiet=quiet)

    summary = {
        "total_groups":  len(groups),
        "total_msgs":    len(all_msgs),
        "private_msgs":  len(private_msgs),
        "photos":        len(photos),
    }

    payload = {
        "meta": {"tool": "Red Phantom", "version": "7.0-prod",
                 "timestamp": datetime.now(timezone.utc).isoformat(),
                 "target": user_data.get("username") or str(user_data["id"])},
        "user": user_data,
        "username_history": history,
        "geo": geo,
        "photos": photos,
        "groups": groups,
        "private_messages": private_msgs,
        "mentions": mentions,
        "activity": activity,
        "summary": summary,
    }

    section("Export", "💾", quiet=quiet)
    tgt = user_data.get("username") or str(user_data["id"])
    json_path = export_json(payload, tgt, quiet=quiet)
    csv_path  = export_csv(payload, tgt, quiet=quiet)
    html_path = export_html(payload, tgt, quiet=quiet)

    if notifier and BOT_CONFIG.get("send_files", True):
        section("Send to Bot", "📤", quiet=quiet)
        try:
            await notifier.send_profile_summary(user_data, geo, summary)
        except Exception as e:
            warn(f"Send summary error: {e}")
        for path, caption in [
            (json_path, "📄 Full data (JSON)"),
            (csv_path,  "📊 Messages (CSV)"),
            (html_path, "🎨 Visual (HTML)"),
        ]:
            if path and Path(path).exists():
                try:
                    await notifier.send_file(path, caption)
                except Exception:
                    pass

    return payload


# ══════════════════════════════════════════════════════════════════
# BOT HANDLERS
# ══════════════════════════════════════════════════════════════════
def register_bot_handlers(bot: Client, userbot: Client, notifier: BotNotifier):
    admin_filter = filters.user(BOT_CONFIG["admin_ids"])

    @bot.on_message(filters.command("start") & admin_filter)
    async def cmd_start(_, message: Message):
        try:
            await message.reply(
                "🩸 **RED PHANTOM BOT**\n\n"
                "**Commands:**\n"
                "• `/scan @username [limit]` — scan lengkap\n"
                "• `/quick @username` — profil + geo\n"
                "• `/monitor @username` — monitor real-time\n"
                "• `/stopmonitor` — stop semua\n"
                "• `/status` — status\n"
                "• `/help` — bantuan\n\n"
                "Hasil scan otomatis dikirim: Summary · JSON · CSV · HTML"
            )
        except Exception as e:
            warn(f"cmd_start error: {e}")

    @bot.on_message(filters.command("help") & admin_filter)
    async def cmd_help(_, message: Message):
        await cmd_start(_, message)

    @bot.on_message(filters.command("status") & admin_filter)
    async def cmd_status(_, message: Message):
        try:
            me_user = await userbot.get_me()
            me_bot = await bot.get_me()
            state = load_bot_state()
            monitors = len(state.get("monitors", {}))
            await message.reply(
                f"📊 **STATUS**\n\n"
                f"🤖 Bot: `@{me_bot.username}`\n"
                f"👤 Userbot: `@{me_user.username or me_user.id}`\n"
                f"🕐 `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`\n"
                f"🎯 Admins: `{len(BOT_CONFIG['admin_ids'])}`\n"
                f"🔴 Monitors: `{monitors}`"
            )
        except Exception as e:
            await message.reply(f"❌ `{md_escape(str(e), 200)}`")

    @bot.on_message(filters.command("scan") & admin_filter)
    async def cmd_scan(_, message: Message):
        try:
            args = message.text.split()
            if len(args) < 2:
                await message.reply("❌ Usage: `/scan @username [limit]`")
                return
            target = args[1]
            limit = int(args[2]) if len(args) > 2 and args[2].isdigit() else BOT_CONFIG["default_msg_limit"]

            await message.reply(
                f"🔍 **Scan started** `{target}` (limit {limit})\n"
                f"⏳ Hasil akan dikirim otomatis saat selesai."
            )

            async def _do_scan():
                try:
                    user = await userbot.get_users(target)
                    await scan_and_export(
                        userbot, user, limit, notifier=notifier,
                        max_scan=BOT_CONFIG["default_max_scan"],
                        download=False,
                        max_mb=BOT_CONFIG["default_max_mb"],
                        quiet=True,
                    )
                    await notifier.send_text(f"✅ **Scan complete** `@{user.username or user.id}`")
                except PeerIdInvalid:
                    await notifier.send_text(f"❌ Target `{target}` tidak ditemukan.")
                except Exception as e:
                    await notifier.send_text(f"❌ Scan error: `{md_escape(str(e), 200)}`")

            asyncio.create_task(_do_scan())
        except Exception as e:
            await message.reply(f"❌ `{md_escape(str(e), 200)}`")

    @bot.on_message(filters.command("quick") & admin_filter)
    async def cmd_quick(_, message: Message):
        try:
            args = message.text.split()
            if len(args) < 2:
                await message.reply("❌ Usage: `/quick @username`")
                return
            target = args[1]
            await message.reply(f"⚡ Quick scan `{target}`...")
            user = await userbot.get_users(target)
            user_data = await read_profile(userbot, user, quiet=True)
            geo = geo_from_bio(user_data.get("bio") or "")
            summary = {"total_groups": 0, "total_msgs": 0, "private_msgs": 0, "photos": 0}
            await notifier.send_profile_summary(user_data, geo, summary)
            await message.reply("✅ Quick scan selesai.")
        except PeerIdInvalid:
            await message.reply("❌ Target tidak ditemukan.")
        except Exception as e:
            await message.reply(f"❌ `{md_escape(str(e), 200)}`")

    @bot.on_message(filters.command("monitor") & admin_filter)
    async def cmd_monitor(_, message: Message):
        try:
            args = message.text.split()
            if len(args) < 2:
                await message.reply("❌ Usage: `/monitor @username`")
                return
            target = args[1]
            user = await userbot.get_users(target)

            state = load_bot_state()
            if str(user.id) in state.get("monitors", {}):
                await message.reply(f"⚠ Monitor `@{user.username or user.id}` sudah aktif.")
                return

            state.setdefault("monitors", {})[str(user.id)] = {
                "username": user.username,
                "started": datetime.now(timezone.utc).isoformat(),
            }
            save_bot_state(state)

            asyncio.create_task(monitor_with_bot(userbot, user, notifier, interval=60))

            await message.reply(
                f"🔴 **Monitor started** `@{user.username or user.id}`\n"
                f"Interval: 60s · Stop: `/stopmonitor`"
            )
        except PeerIdInvalid:
            await message.reply("❌ Target tidak ditemukan.")
        except Exception as e:
            await message.reply(f"❌ `{md_escape(str(e), 200)}`")

    @bot.on_message(filters.command("stopmonitor") & admin_filter)
    async def cmd_stopmonitor(_, message: Message):
        try:
            state = load_bot_state()
            count = len(state.get("monitors", {}))
            state["monitors"] = {}
            save_bot_state(state)
            await message.reply(f"⏹ {count} monitor dihentikan.")
        except Exception as e:
            await message.reply(f"❌ `{md_escape(str(e), 200)}`")

    @bot.on_message(filters.private & ~admin_filter)
    async def deny(_, message: Message):
        try:
            await message.reply("🚫 Akses ditolak. Admin only.")
        except Exception:
            pass

    success("Bot handlers registered.")


# ══════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════
def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            return json.load(open(CONFIG_FILE))
        except Exception:
            return {}
    return {}


def save_config(api_id, api_hash, session_name):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"api_id": api_id, "api_hash": api_hash,
                       "session_name": session_name}, f, indent=4)
        success("Config tersimpan.")
    except Exception as e:
        error(f"Save config error: {e}")


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
    if not api_id or not api_hash:
        error("API ID / Hash kosong!")
        sys.exit(1)
    save_config(api_id, api_hash, session)
    return {"api_id": api_id, "api_hash": api_hash, "session_name": session}


# ══════════════════════════════════════════════════════════════════
# RESOLVER
# ══════════════════════════════════════════════════════════════════
async def resolve_target(client: Client):
    section("Input Target", "🎯")
    print(colored("    Format: @username | username | ID | +628xxx", "white"))
    raw = ask("Target")
    if not raw:
        return None
    raw = raw.strip()

    if raw.startswith("@"):
        candidate = raw
    elif raw.replace("+", "").replace("-", "").replace(" ", "").isdigit() and len(raw) > 8:
        candidate = raw if raw.startswith("+") else "+" + raw.lstrip("+")
    elif raw.isdigit():
        candidate = int(raw)
    else:
        candidate = raw

    info(f"Resolve: {candidate}")
    try:
        user = await client.get_users(candidate)
        success(f"OK → {user.first_name} (@{user.username or 'None'}) — {user.id}")
        return user
    except (PeerIdInvalid, UsernameInvalid, UsernameNotOccupied):
        error(f"Target '{raw}' tidak ditemukan.")
        if ask_yes_no("Coba lain?", "y"):
            return await resolve_target(client)
        return None
    except FloodWait as fw:
        warn(f"FloodWait {fw.value}s")
        await asyncio.sleep(fw.value + 1)
        return await resolve_target(client)
    except Exception as e:
        error(f"Error: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
# MENU
# ══════════════════════════════════════════════════════════════════
def main_menu() -> dict:
    section("Menu Scrape", "☰")
    print(colored("    1. Full Read (semua)", BRIGHT_RED))
    print(colored("    2. Profile + Bio + Photos", BRIGHT_RED))
    print(colored("    3. Groups + Messages", BRIGHT_RED))
    print(colored("    4. Private Chat", BRIGHT_RED))
    print(colored("    5. Mention Analysis", BRIGHT_RED))
    print(colored("    6. Activity Analysis", BRIGHT_RED))
    print(colored("    7. Saved Messages", BRIGHT_RED))
    print(colored("    8. Contacts", BRIGHT_RED))
    print(colored("    9. Real-time Monitor", BRIGHT_RED))
    print(colored("    0. Keluar", BRIGHT_RED))

    choice = ask("Pilihan (0-9)", default="1")
    presets = {
        "1": {"profile":True,"photos":True,"groups":True,"private":True,
              "mentions":True,"activity":True,"saved":True,"contacts":True,
              "monitor":False},
        "2": {"profile":True,"photos":True,"groups":False,"private":False,
              "mentions":False,"activity":False,"saved":False,"contacts":False,
              "monitor":False},
        "3": {"profile":True,"photos":False,"groups":True,"private":False,
              "mentions":False,"activity":True,"saved":False,"contacts":False,
              "monitor":False},
        "4": {"profile":True,"photos":False,"groups":False,"private":True,
              "mentions":False,"activity":True,"saved":False,"contacts":False,
              "monitor":False},
        "5": {"profile":True,"photos":False,"groups":True,"private":False,
              "mentions":True,"activity":False,"saved":False,"contacts":False,
              "monitor":False},
        "6": {"profile":True,"photos":False,"groups":True,"private":True,
              "mentions":False,"activity":True,"saved":False,"contacts":False,
              "monitor":False},
        "7": {"profile":False,"photos":False,"groups":False,"private":False,
              "mentions":False,"activity":False,"saved":True,"contacts":False,
              "monitor":False},
        "8": {"profile":False,"photos":False,"groups":False,"private":False,
              "mentions":False,"activity":False,"saved":False,"contacts":True,
              "monitor":False},
        "9": {"profile":True,"photos":False,"groups":False,"private":False,
              "mentions":False,"activity":False,"saved":False,"contacts":False,
              "monitor":True},
        "0": None,
    }
    return presets.get(choice)


# ══════════════════════════════════════════════════════════════════
# RUN MANUAL
# ══════════════════════════════════════════════════════════════════
async def run_manual(userbot: Client, notifier: BotNotifier):
    user = await resolve_target(userbot)
    if not user:
        return

    opts = main_menu()
    if opts is None:
        info("Keluar.")
        return

    section("Parameter Scrape", "⚙")
    msg_limit = ask_int("Limit pesan per chat (0=unlimited)",
                        default=BOT_CONFIG["default_msg_limit"], min_val=0)
    max_scan  = ask_int("Max pesan scan per chat",
                        default=BOT_CONFIG["default_max_scan"], min_val=1)
    download  = ask_yes_no("Download media?", "n")
    max_mb    = ask_int("Max media MB",
                        default=BOT_CONFIG["default_max_mb"], min_val=1) if download else 20

    if opts.get("monitor"):
        interval = ask_int("Monitor interval detik", default=60, min_val=10)
        try:
            await notifier.send_text(
                f"🔴 **Monitor started** `@{user.username or user.id}` (interval {interval}s)")
        except Exception:
            pass
        state = load_bot_state()
        state.setdefault("monitors", {})[str(user.id)] = {
            "username": user.username,
            "started": datetime.now(timezone.utc).isoformat(),
        }
        save_bot_state(state)
        await monitor_with_bot(userbot, user, notifier, interval=interval)
        return

    # Scan
    if opts.get("profile") and not (opts.get("groups") or opts.get("private")):
        # Profil saja
        user_data = await read_profile(userbot, user, quiet=False)
        history = track_username(user, quiet=False)
        geo = geo_from_bio(user_data.get("bio") or "")
        show_geo(geo)
        if opts.get("photos"):
            photos = await read_profile_photos(userbot, user, download=download, quiet=False)
            summary = {"total_groups":0,"total_msgs":0,"private_msgs":0,"photos":len(photos)}
        else:
            photos = []
            summary = {"total_groups":0,"total_msgs":0,"private_msgs":0,"photos":0}
        payload = {
            "meta": {"tool": "Red Phantom", "version": "7.0-prod",
                     "timestamp": datetime.now(timezone.utc).isoformat(),
                     "target": user_data.get("username") or str(user_data["id"])},
            "user": user_data, "username_history": history, "geo": geo,
            "photos": photos, "groups": [], "private_messages": [],
            "mentions": {}, "activity": {}, "summary": summary,
        }
        tgt = user_data.get("username") or str(user_data["id"])
        export_json(payload, tgt, quiet=False)
        export_html(payload, tgt, quiet=False)
        try:
            await notifier.send_profile_summary(user_data, geo, summary)
        except Exception:
            pass
    else:
        await scan_and_export(userbot, user, msg_limit, notifier=notifier,
                              max_scan=max_scan, download=download,
                              max_mb=max_mb, quiet=False)

    if opts.get("saved"):
        try:
            await read_saved(userbot, quiet=False)
        except Exception:
            pass
    if opts.get("contacts"):
        try:
            await read_contacts(userbot, quiet=False)
        except Exception:
            pass

    cprint("\n  ══ SELESAI ══", RED, attrs=["bold"])


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
async def main():
    banner()

    if BOT_CONFIG["bot_token"] == "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ":
        error("GANTI BOT_CONFIG['bot_token'] dulu!")
        sys.exit(1)
    if not BOT_CONFIG["admin_ids"] or BOT_CONFIG["admin_ids"][0] == 123456789:
        error("GANTI BOT_CONFIG['admin_ids'] dulu!")
        sys.exit(1)

    config = get_config()

    userbot = Client(
        config["session_name"],
        api_id=int(config["api_id"]),
        api_hash=config["api_hash"],
    )
    bot = Client(
        "red_phantom_bot",
        api_id=int(config["api_id"]),
        api_hash=config["api_hash"],
        bot_token=BOT_CONFIG["bot_token"],
    )
    notifier = BotNotifier(bot, BOT_CONFIG["admin_ids"])

    # Start paralel
    try:
        await asyncio.gather(userbot.start(), bot.start())
        success("Userbot + Bot online")
    except AuthKeyUnregistered:
        error("Session invalid. Hapus *.session, jalankan ulang.")
        sys.exit(1)
    except Exception as e:
        error(f"Start error: {e}")
        sys.exit(1)

    try:
        me_bot = await bot.get_me()
        me_user = await userbot.get_me()
        success(f"Bot: @{me_bot.username}")
        success(f"Userbot: @{me_user.username or me_user.id}")
    except Exception as e:
        warn(f"get_me error: {e}")
        me_bot = me_user = None

    register_bot_handlers(bot, userbot, notifier)

    if me_bot and me_user:
        try:
            await notifier.send_text(
                f"🩸 **RED PHANTOM ONLINE**\n\n"
                f"Bot: `@{me_bot.username}`\n"
                f"Userbot: `@{me_user.username or me_user.id}`\n"
                f"Time: `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`\n\n"
                f"Ketik `/help`"
            )
        except Exception as e:
            warn(f"Welcome error: {e}")

    try:
        while True:
            section("Menu Utama", "◆")
            print(colored("    1. Scan target", BRIGHT_RED))
            print(colored("    2. Monitor target", BRIGHT_RED))
            print(colored("    3. Keluar", BRIGHT_RED))
            print(colored("\n    💡 Bisa juga ketik /scan di bot", "cyan"))

            choice = ask("Pilihan (1-3)", default="1")
            if choice == "3":
                break
            elif choice == "1":
                try:
                    await run_manual(userbot, notifier)
                except Exception as e:
                    error(f"Scan error: {e}")
            elif choice == "2":
                user = await resolve_target(userbot)
                if user:
                    interval = ask_int("Interval detik", default=60, min_val=10)
                    state = load_bot_state()
                    state.setdefault("monitors", {})[str(user.id)] = {
                        "username": user.username,
                        "started": datetime.now(timezone.utc).isoformat(),
                    }
                    save_bot_state(state)
                    try:
                        await notifier.send_text(
                            f"🔴 Monitor `@{user.username or user.id}` started")
                    except Exception:
                        pass
                    try:
                        await monitor_with_bot(userbot, user, notifier, interval=interval)
                    except KeyboardInterrupt:
                        state = load_bot_state()
                        state.get("monitors", {}).pop(str(user.id), None)
                        save_bot_state(state)
            else:
                warn("Pilihan tidak valid.")
    except KeyboardInterrupt:
        cprint("\n  [!] Dibatalkan.", YELLOW)

    # Cleanup
    try:
        await notifier.send_text("⏹ **OFFLINE**")
    except Exception:
        pass
    for cli, name in [(bot, "bot"), (userbot, "userbot")]:
        try:
            await cli.stop()
        except Exception:
            pass
    cprint("\n  ══ BYE ══\n", RED, attrs=["bold"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        cprint("\n\n  [!] Dibatalkan.\n", RED, attrs=["bold"])
        sys.exit(0)
    except Exception as e:
        import traceback
        traceback.print_exc()
        cprint(f"\n  [FATAL] {e}\n", RED, attrs=["bold"])
        sys.exit(1)
