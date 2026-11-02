#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║   RED PHANTOM OSINT — BOT INTEGRATION EDITION                        ║
║   Manual Input · Full Read · Bot Notif · Real-Time Monitor          ║
║   Powered by Yusiqo · Untuk penggunaan yang SAH & BERIZIN saja      ║
╚══════════════════════════════════════════════════════════════════════╝

  FITUR BARU (vs versi sebelumnya):
    ✅ Kirim hasil scrape ke BOT Telegram Anda (real-time)
    ✅ Terima notifikasi perubahan profil via bot
    ✅ Kirim file JSON/CSV/HTML otomatis ke chat Anda
    ✅ Bot commands: /start, /scan, /monitor, /status, /help
    ✅ Hanya admin ID yang bisa kontrol bot
"""

import os
import sys
import re
import json
import csv
import io
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

from pyrogram import Client, filters
from pyrogram.errors import (
    PeerIdInvalid, UsernameInvalid, UsernameNotOccupied,
    FloodWait, ChatAdminRequired, UserNotParticipant,
    ChannelPrivate, ChatForbidden, AuthKeyUnregistered,
    MessageTooLong, BotMethodInvalid,
)
from pyrogram.types import User, Message
from pyfiglet import figlet_format
from termcolor import colored


# ══════════════════════════════════════════════════════════════════
# ⚙  KONFIGURASI BOT & OPERATOR — EDIT DI SINI
# ══════════════════════════════════════════════════════════════════
BOT_CONFIG = {
    # Token bot dari @BotFather (WAJIB)
    "bot_token": "8831458505:AAFv8SB4O6eAwSdISxfEQ9YXZwrR34ZN3C4",

    # ID Telegram Anda (WAJIB) — dari @userinfobot
    # Bisa lebih dari 1 ID (list) untuk multiple admin
    "admin_ids": [8466466096],

    # Kirim notifikasi real-time ke bot saat monitor?
    "notify_realtime": True,

    # Kirim file JSON/CSV/HTML ke chat bot?
    "send_files": True,

    # Auto-start bot di background saat script jalan?
    "start_bot": True,
}


# ══════════════════════════════════════════════════════════════════
# GLOBAL
# ══════════════════════════════════════════════════════════════════
CONFIG_FILE   = "config.json"
REPORT_DIR    = Path("reports")
MEDIA_DIR     = REPORT_DIR / "media"
HISTORY_DIR   = Path("history")
BOT_STATE     = Path("bot_state.json")

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
    cprint("   ⚡  TELEGRAM OSINT · MANUAL · FULL READ · BOT  ⚡", RED, attrs=["bold"])
    cprint(f"  {line}", RED)
    cprint("   ▸ Tool    : Red Phantom — Bot Integration", BRIGHT_RED)
    cprint("   ▸ Author  : Yusiqo", BRIGHT_RED)
    cprint("   ▸ Mode    : Manual input + Full Read + Bot notif", BRIGHT_RED)
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
# 🆕 BOT NOTIFIER — kirim hasil ke bot
# ══════════════════════════════════════════════════════════════════
class BotNotifier:
    """Wrapper untuk kirim notifikasi via bot Telegram ke admin."""
    def __init__(self, bot_client: Client, admin_ids: list):
        self.bot = bot_client
        self.admin_ids = admin_ids

    async def send_text(self, text: str, markdown=True):
        """Kirim teks ke semua admin."""
        for aid in self.admin_ids:
            try:
                # Split kalau kepanjangan
                chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
                for chunk in chunks:
                    try:
                        await self.bot.send_message(
                            aid, chunk,
                            parse_mode="markdown" if markdown else None,
                            disable_web_page_preview=True,
                        )
                    except MessageTooLong:
                        await self.bot.send_message(aid, chunk[:4000])
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
            except Exception as e:
                warn(f"Bot send error: {e}")

    async def send_file(self, filepath: str, caption=""):
        """Kirim file ke semua admin."""
        for aid in self.admin_ids:
            try:
                await self.bot.send_document(aid, filepath, caption=caption)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
            except Exception as e:
                warn(f"Bot file error: {e}")

    async def send_profile_summary(self, user_data: dict, geo: dict, summary: dict):
        """Kirim ringkasan profil dalam format cantik."""
        u = user_data
        md = f"""🩸 **RED PHANTOM — SCAN RESULT**

👤 **Target**
• Username: `@{u.get('username') or 'None'}`
• Name: **{u.get('first_name') or ''} {u.get('last_name') or ''}**
• ID: `{u.get('id')}`
• Phone: `{u.get('phone') or 'Hidden'}`
• DC: `{u.get('dc_id')}`
• Status: `{u.get('status') or 'None'}`
• Language: `{u.get('language') or 'None'}`

📝 **Bio**
`{u.get('bio') or 'None'}`

🏷 **Flags**
• Bot: `{u.get('is_bot')}`
• Verified: `{u.get('is_verified')}`
• Premium: `{u.get('is_premium')}`
• Scam: `{u.get('is_scam')}`
• Fake: `{u.get('is_fake')}`

🌍 **Geo (dari bio)**
• Country: `{geo.get('country') or '-'}`
• City: `{geo.get('city') or '-'}`
• Maps: `{geo.get('maps_link') or '-'}`

📊 **Summary**
• Groups: `{summary.get('total_groups', 0)}`
• Messages: `{summary.get('total_msgs', 0)}`
• Private: `{summary.get('private_msgs', 0)}`
• Photos: `{summary.get('photos', 0)}`
"""
        await self.send_text(md)

    async def send_change_alert(self, user: User, changes: list):
        """Kirim notif real-time perubahan profil."""
        md = f"🚨 **PROFILE CHANGE DETECTED**\n\n"
        md += f"👤 `@{user.username or 'None'}` ({user.id})\n\n"
        for ch in changes:
            md += f"▸ **{ch['field']}**\n"
            md += f"   Old: `{str(ch['old'])[:80]}`\n"
            md += f"   New: `{str(ch['new'])[:80]}`\n\n"
        md += f"🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        await self.send_text(md)

    async def send_new_message(self, user: User, msg: dict):
        """Kirim notif pesan baru masuk dari target."""
        md = f"💬 **NEW MESSAGE from** `@{user.username or user.id}`\n\n"
        md += f"🕐 `{msg['date']}`\n"
        md += f"📝 {msg['text'][:500]}"
        await self.send_text(md)


# ══════════════════════════════════════════════════════════════════
# 🆕 BOT COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════
def register_bot_handlers(bot: Client, userbot: Client, notifier: BotNotifier):
    """Daftarkan command handler untuk bot."""

    def is_admin(_, __, message: Message):
        return message.from_user and message.from_user.id in BOT_CONFIG["admin_ids"]

    admin_filter = filters.create(is_admin)

    @bot.on_message(filters.command("start") & admin_filter)
    async def cmd_start(_, message: Message):
        text = """🩸 **RED PHANTOM BOT**

Selamat datang, admin!

**Commands:**
• `/scan @username` — scan target (default limit 100)
• `/scan @username 50` — scan dengan limit pesan 50
• `/quick @username` — quick scan (profil + geo saja)
• `/monitor @username` — monitor real-time perubahan
• `/stopmonitor` — stop semua monitor
• `/status` — status bot & sistem
• `/help` — bantuan

**Hasil scan akan dikirim otomatis:**
✅ Summary di chat
✅ File JSON (data lengkap)
✅ File CSV (pesan → Excel)
✅ File HTML (report visual)
"""
        await message.reply(text)

    @bot.on_message(filters.command("help") & admin_filter)
    async def cmd_help(_, message: Message):
        await cmd_start(_, message)

    @bot.on_message(filters.command("status") & admin_filter)
    async def cmd_status(_, message: Message):
        me_user = await userbot.get_me()
        me_bot = await bot.get_me()
        text = f"""📊 **STATUS**

🤖 Bot: `@{me_bot.username}`
👤 Userbot: `@{me_user.username or me_user.id}`
🕐 Time: `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`
📁 Reports: `{REPORT_DIR.absolute()}`
🎯 Admins: `{len(BOT_CONFIG['admin_ids'])}`
"""
        await message.reply(text)

    @bot.on_message(filters.command("scan") & admin_filter)
    async def cmd_scan(_, message: Message):
        args = message.text.split()
        if len(args) < 2:
            await message.reply("❌ Usage: `/scan @username [limit]`")
            return

        target = args[1]
        limit = int(args[2]) if len(args) > 2 and args[2].isdigit() else 100

        await message.reply(f"🔍 Scanning `{target}` (limit {limit})...\n⏳ Mohon tunggu...")

        try:
            user = await userbot.get_users(target)
        except Exception as e:
            await message.reply(f"❌ Target tidak ditemukan: `{e}`")
            return

        # Jalankan scrape
        payload = await scan_and_export(userbot, user, limit, notifier=notifier)
        if payload:
            await message.reply(f"✅ Scan selesai untuk `@{user.username or user.id}`")

    @bot.on_message(filters.command("quick") & admin_filter)
    async def cmd_quick(_, message: Message):
        args = message.text.split()
        if len(args) < 2:
            await message.reply("❌ Usage: `/quick @username`")
            return
        target = args[1]
        await message.reply(f"⚡ Quick scan `{target}`...")
        try:
            user = await userbot.get_users(target)
        except Exception as e:
            await message.reply(f"❌ Error: `{e}`")
            return

        # Quick = profil + geo + photos only
        user_data = await read_profile(userbot, user)
        geo = geo_from_bio(user_data.get("bio") or "")
        summary = {"total_groups": 0, "total_msgs": 0, "private_msgs": 0,
                   "photos": 0}
        await notifier.send_profile_summary(user_data, geo, summary)
        await message.reply("✅ Quick scan selesai.")

    @bot.on_message(filters.command("monitor") & admin_filter)
    async def cmd_monitor(_, message: Message):
        args = message.text.split()
        if len(args) < 2:
            await message.reply("❌ Usage: `/monitor @username`")
            return
        target = args[1]
        await message.reply(f"🔴 Monitor `{target}` dimulai...\n"
                            f"Notif dikirim saat ada perubahan.\n"
                            f"Stop dengan `/stopmonitor`")
        try:
            user = await userbot.get_users(target)
        except Exception as e:
            await message.reply(f"❌ Error: `{e}`")
            return
        # Simpan ke state
        state = load_bot_state()
        state.setdefault("monitors", {})[str(user.id)] = {
            "username": user.username,
            "started":  datetime.now(timezone.utc).isoformat(),
        }
        save_bot_state(state)

        # Jalankan monitor background
        asyncio.create_task(monitor_with_bot(userbot, user, notifier, interval=60))

    @bot.on_message(filters.command("stopmonitor") & admin_filter)
    async def cmd_stopmonitor(_, message: Message):
        state = load_bot_state()
        state["monitors"] = {}
        save_bot_state(state)
        await message.reply("⏹ Semua monitor dihentikan.")

    success("Bot handlers terdaftar.")


def load_bot_state() -> dict:
    if BOT_STATE.exists():
        try:
            return json.load(open(BOT_STATE))
        except Exception:
            return {}
    return {}


def save_bot_state(state: dict):
    with open(BOT_STATE, "w") as f:
        json.dump(state, f, indent=2, default=str)


# ══════════════════════════════════════════════════════════════════
# 🆕 MONITOR WITH BOT NOTIF
# ══════════════════════════════════════════════════════════════════
async def monitor_with_bot(client: Client, user: User,
                           notifier: BotNotifier, interval=60):
    """Monitor real-time dengan notif bot."""
    info(f"Monitor start: @{user.username or user.id} (interval {interval}s)")
    prev = snap_user(user)
    last_mid = 0
    try:
        async for m in client.get_chat_history(user.id, limit=1):
            last_mid = m.id
            break
    except Exception:
        pass

    while True:
        # Cek apakah masih ada di monitors list
        state = load_bot_state()
        if str(user.id) not in state.get("monitors", {}):
            info(f"Monitor stop: @{user.username or user.id}")
            return

        try:
            fresh = await client.get_users(user.id)
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
            continue
        except Exception as e:
            warn(f"Monitor refresh error: {e}")
            await asyncio.sleep(interval)
            continue

        cur = snap_user(fresh)
        diffs = [(k, prev.get(k), cur.get(k)) for k in cur if prev.get(k) != cur.get(k)]

        if diffs:
            info(f"⚠ {len(diffs)} perubahan pada @{fresh.username or fresh.id}")
            changes_list = [{"field": k, "old": o, "new": n} for k, o, n in diffs]
            if BOT_CONFIG.get("notify_realtime", True):
                await notifier.send_change_alert(fresh, changes_list)
            track_username(fresh)

        # Cek pesan baru
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
                    if BOT_CONFIG.get("notify_realtime", True):
                        await notifier.send_new_message(fresh, x)
        except Exception as e:
            warn(f"Monitor msg error: {e}")

        prev = cur
        await asyncio.sleep(interval)


# ══════════════════════════════════════════════════════════════════
# SCAN + EXPORT + SEND TO BOT
# ══════════════════════════════════════════════════════════════════
async def scan_and_export(client: Client, user: User, msg_limit: int,
                          notifier: BotNotifier = None,
                          max_scan: int = 5000,
                          download: bool = False,
                          max_mb: int = 20) -> dict:
    """Scan lengkap + export + kirim ke bot."""
    # Profile
    user_data = await read_profile(client, user)
    history = track_username(user)
    geo = geo_from_bio(user_data.get("bio") or "")
    show_geo(geo)

    # Photos
    photos = await read_profile_photos(client, user, download=download)

    # Groups + private
    groups = await read_common_groups(client, user, msg_limit, max_scan,
                                      download, max_mb, quiet=True)
    private_msgs = await read_private_chat(client, user, msg_limit, max_scan,
                                           download, max_mb, quiet=True)

    # Mentions + activity
    mentions = await analyze_mentions(client, user, groups)
    all_msgs = []
    for g in groups:
        all_msgs.extend(g["messages"])
    all_msgs.extend(private_msgs)
    activity = analyze_activity(all_msgs)

    summary = {
        "total_groups": len(groups),
        "total_msgs":   len(all_msgs),
        "private_msgs": len(private_msgs),
        "photos":       len(photos),
    }

    payload = {
        "meta": {"tool": "Red Phantom", "version": "5.0-bot",
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

    # Export
    section("Export", "💾")
    tgt = user_data.get("username") or str(user_data["id"])
    json_path = export_json(payload, tgt)
    csv_path  = export_csv(payload, tgt)
    html_path = export_html(payload, tgt)

    # KIRIM KE BOT
    if notifier and BOT_CONFIG.get("send_files", True):
        section("Send to Bot", "📤")
        await notifier.send_profile_summary(user_data, geo, summary)

        for path, caption in [
            (json_path, "📄 Full data (JSON)"),
            (csv_path,  "📊 Messages (CSV)"),
            (html_path, "🎨 Visual report (HTML)"),
        ]:
            if path and Path(path).exists():
                await notifier.send_file(path, caption)
                success(f"Terkirim: {Path(path).name}")

    return payload


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
# MENU
# ══════════════════════════════════════════════════════════════════
def main_menu() -> dict:
    section("Menu Scrape", "☰")
    print(colored("    1. Full Read (semua)", BRIGHT_RED))
    print(colored("    2. Profile + Bio + Photos", BRIGHT_RED))
    print(colored("    3. Common Groups + Messages", BRIGHT_RED))
    print(colored("    4. Private Chat History", BRIGHT_RED))
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
# RESOLVER
# ══════════════════════════════════════════════════════════════════
async def resolve_target(client: Client):
    section("Input Target (Manual)", "🎯")
    print(colored("    Format: @username | username | ID | +628xxx", "white"))
    raw = ask("Target").strip()

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
        await asyncio.sleep(fw.value)
        return await resolve_target(client)
    except Exception as e:
        error(f"Error: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
# (Bagian read_profile, read_profile_photos, geo, track_username,
#  read_common_groups, read_private_chat, analyze_mentions,
#  analyze_activity, read_saved, read_contacts, export_json,
#  export_csv, export_html, snap_user, media_label, try_download
#  → SAMA PERSIS dengan kode lama Anda. Tidak diubah sama sekali.)
# ══════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────
# SEMUA FUNGSI DI BAWAH INI DI-COPY DARI KODE LAMA ANDA — TIDAK DIUBAH
# ──────────────────────────────────────────────────────────────────

async def read_profile(client: Client, user: User) -> dict:
    section("Full Profile Read", "🎯")
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
        "is_contact": user.is_contact if hasattr(user, "is_contact") else None,
        "is_mutual_contact": user.is_mutual_contact if hasattr(user, "is_mutual_contact") else None,
        "is_deleted": user.is_deleted if hasattr(user, "is_deleted") else None,
        "photo": None,
    }
    if user.photo:
        data["photo"] = {
            "small_file_id": user.photo.small_file_id,
            "big_file_id":   user.photo.big_file_id,
            "dc_id":         user.photo.dc_id,
        }
    kv("ID", data["id"], RED)
    kv("Username", f"@{data['username']}" if data["username"] else "None", RED)
    kv("First Name", data["first_name"] or "None")
    kv("Last Name", data["last_name"] or "None")
    kv("Phone", data["phone"] or "Hidden", "yellow")
    kv("DC ID", data["dc_id"])
    kv("Language", data["language"] or "None")
    kv("Status", data["status"] or "None")
    kv("Bio", data["bio"] or "None", "cyan")
    print()
    kv("Bot", "Yes" if data["is_bot"] else "No")
    kv("Verified", "Yes" if data["is_verified"] else "No", "cyan")
    kv("Premium", "Yes" if data["is_premium"] else "No", "cyan")
    kv("Support", "Yes" if data["is_support"] else "No")
    kv("Contact", data["is_contact"] if data["is_contact"] is not None else "N/A")
    kv("Mutual", data["is_mutual_contact"] if data["is_mutual_contact"] is not None else "N/A")
    kv("Deleted", data["is_deleted"] if data["is_deleted"] is not None else "N/A")
    kv("Restricted", "Yes" if data["is_restricted"] else "No")
    kv("Scam", "Yes" if data["is_scam"] else "No", "red" if data["is_scam"] else "white")
    kv("Fake", "Yes" if data["is_fake"] else "No", "red" if data["is_fake"] else "white")
    kv("Has Photo", "Yes" if data["photo"] else "No")
    return data


async def read_profile_photos(client: Client, user: User, limit=20, download=False) -> list:
    section("Profile Photos", "📸")
    photos = []
    try:
        async for photo in client.get_chat_photos(user.id, limit=limit):
            entry = {"date": str(photo.date), "file_id": photo.file_id,
                     "dc_id": photo.dc_id, "local_path": None}
            kv("Photo", f"{photo.date} | dc={photo.dc_id} | {photo.file_id[:22]}...")
            if download:
                try:
                    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                    fname = f"profile_{user.id}_{photo.date.strftime('%Y%m%d_%H%M%S')}.jpg"
                    path = await client.download_media(photo.file_id, file_name=str(MEDIA_DIR / fname))
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
    result = {"coordinates": None, "maps_link": None, "country": None, "city": None, "hits": []}
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
    mm = re.search(r"(https?://(?:www\.)?(?:maps\.google\.com|goo\.gl/maps|maps\.app\.goo\.gl|yandex\.com/maps)[^\s]*)", bio)
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
    section("Geolocation", "🌍")
    if not any([geo["coordinates"], geo["maps_link"], geo["country"], geo["city"]]):
        warn("Tidak ada info lokasi.")
        return
    if geo["coordinates"]:
        kv("Coordinates", f"{geo['coordinates']['lat']}, {geo['coordinates']['lon']}", RED)
    if geo["maps_link"]:
        kv("Maps Link", geo["maps_link"], "cyan")
    if geo["country"]:
        kv("Country", geo["country"], RED)
    if geo["city"]:
        kv("City", geo["city"])
    if geo["hits"]:
        kv("Hints", ", ".join(geo["hits"]), "yellow")


def track_username(user: User) -> dict:
    section("Username History", "🔗")
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
    with open(file, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False, default=str)
    kv("Current", f"@{user.username}" if user.username else "None", RED)
    kv("Snapshots", len(history))
    if prev:
        kv("Previous", ", ".join(f"@{u}" for u in set(prev)))
    if changed and len(history) > 1:
        warn("Username BERUBAH!")
    elif changed:
        info("Snapshot pertama.")
    return {"current": user.username, "history": history, "changed": changed}


def media_label(message) -> str:
    if not message.media:
        return ""
    mt = message.media.value if hasattr(message.media, "value") else str(message.media)
    return f"[{mt}]"


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
        warn(f"Skip media {size_mb:.1f}MB")
        return None
    try:
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        fname = f"msg_{user_id}_{message.id}"
        path = await client.download_media(message, file_name=str(MEDIA_DIR / fname))
        return str(path) if path else None
    except Exception as e:
        warn(f"Gagal download: {e}")
        return None


async def read_common_groups(client: Client, user: User, msg_limit: int,
                             max_scan: int, download_media: bool,
                             max_mb: int, quiet: bool) -> list:
    section("Common Groups & Messages", "🌐")
    results = []
    try:
        common = await client.get_common_chats(user.id)
    except FloodWait as fw:
        await asyncio.sleep(fw.value)
        return results
    except Exception as e:
        error(f"Gagal: {e}")
        return results
    if not common:
        warn("Tidak ada grup bersama.")
        return results
    info(f"Total grup bersama: {len(common)}")
    for idx, chat in enumerate(common, 1):
        progress_bar(idx, len(common), prefix=f"Grup {idx}")
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
                        entry["media_path"] = await try_download(client, message, user.id, max_mb)
                    messages.append(entry)
                    count += 1
                    if msg_limit > 0 and count >= msg_limit:
                        break
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
        except (ChatAdminRequired, UserNotParticipant, ChannelPrivate, ChatForbidden):
            warn(f"Tidak ada akses {chat_data['title']}")
        except Exception as e:
            error(f"Error di {chat_data['title']}: {e}")
        results.append({"chat": chat_data, "messages": messages,
                        "scanned": scanned, "found": count})
    return results


async def read_private_chat(client: Client, user: User, msg_limit: int,
                            max_scan: int, download_media: bool,
                            max_mb: int, quiet: bool) -> list:
    section("Private Chat History", "💬")
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
                entry["media_path"] = await try_download(client, m, user.id, max_mb)
            messages.append(entry)
            count += 1
            if msg_limit > 0 and count >= msg_limit:
                break
        if count == 0:
            warn("Tidak ada private chat.")
        else:
            info(f"→ {count} pesan.")
    except Exception as e:
        warn(f"Error: {e}")
    return messages


async def analyze_mentions(client: Client, user: User, groups: list,
                           limit_per_chat=1000) -> dict:
    section("Mention Analysis", "🎯")
    if not groups:
        warn("Tidak ada grup.")
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
        except Exception:
            pass
    print(colored(f"\n   Pesan dianalisis: {total}", BRIGHT_RED, attrs=["bold"]))
    if mentioned_by:
        print(colored("\n   ▸ Top mention target:", BRIGHT_RED, attrs=["bold"]))
        for k, c in mentioned_by.most_common(10):
            kv(k, c, RED)
    if mentioned_users:
        print(colored("\n   ▸ Top di-mention target:", BRIGHT_RED, attrs=["bold"]))
        for k, c in mentioned_users.most_common(10):
            kv(k, c, RED)
    return {"total_analyzed": total,
            "mentioned_by": mentioned_by.most_common(20),
            "mentioned_users": mentioned_users.most_common(20),
            "replied_to": replied_to.most_common(20)}


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
    print(colored("\n   Jam aktif:", BRIGHT_RED, attrs=["bold"]))
    for h in range(24):
        bar = "█" * int(hours[h] / max(1, max(hours)) * 20)
        print(colored(f"    {h:02d}:00 │{bar:<20}│ {hours[h]}", RED))
    print(colored("\n   Hari aktif:", BRIGHT_RED, attrs=["bold"]))
    for i, d in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
        bar = "█" * int(weekdays[i] / max(1, max(weekdays)) * 20)
        print(colored(f"    {d} │{bar:<20}│ {weekdays[i]}", RED))
    kv("Peak Hour", f"{peak_h:02d}:00", RED)
    kv("Peak Day", peak_d, RED)
    kv("Est. TZ", f"UTC{est_tz:+d}", "yellow")
    return {"hourly": hours, "weekday": weekdays,
            "peak_hour": peak_h, "peak_day": peak_d, "est_tz": est_tz}


async def read_saved(client: Client, limit=100) -> list:
    section("Saved Messages", "📥")
    msgs = []
    try:
        async for m in client.get_chat_history("me", limit=limit):
            text = m.text or media_label(m) or "[empty]"
            msgs.append({"date": m.date.strftime("%Y-%m-%d %H:%M:%S"),
                         "text": text, "message_id": m.id})
        if not msgs:
            warn("Kosong.")
    except Exception as e:
        error(f"Gagal: {e}")
    return msgs


async def read_contacts(client: Client, limit=500) -> list:
    section("Contacts", "📇")
    contacts = []
    try:
        async for c in client.get_contacts(limit=limit):
            contacts.append({"id": c.id, "username": c.username,
                             "first_name": c.first_name, "last_name": c.last_name,
                             "phone": c.phone_number})
        info(f"Total: {len(contacts)}")
    except Exception as e:
        error(f"Gagal: {e}")
    return contacts


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
    success(f"HTML → {path}")
    return str(path)


def snap_user(u: User) -> dict:
    return {
        "username": u.username, "first_name": u.first_name,
        "last_name": u.last_name, "phone": u.phone_number,
        "bio": getattr(u, "bio", None),
        "status": str(u.status) if u.status else None,
        "photo": (u.photo.big_file_id if u.photo else None),
    }


# ══════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR (MANUAL)
# ══════════════════════════════════════════════════════════════════
async def run_manual(userbot: Client, notifier: BotNotifier):
    """Mode manual: input target + menu + scan + kirim ke bot."""
    user = await resolve_target(userbot)
    if not user:
        return

    opts = main_menu()
    if opts is None:
        info("Keluar.")
        return

    section("Parameter Scrape", "⚙")
    msg_limit = ask_int("Limit pesan per chat (0=unlimited)", default=100, min_val=0)
    max_scan  = ask_int("Max pesan scan per chat", default=5000, min_val=1)
    download  = ask_yes_no("Download media?", "n")
    max_mb    = ask_int("Max media MB", default=20, min_val=1) if download else 20

    if opts.get("monitor"):
        # Monitor mode
        interval = ask_int("Monitor interval detik", default=60, min_val=10)
        await notifier.send_text(
            f"🔴 **Monitor started** untuk `@{user.username or user.id}`\n"
            f"Interval: `{interval}s`\n"
            f"Notif real-time dikirim ke sini."
        )
        state = load_bot_state()
        state.setdefault("monitors", {})[str(user.id)] = {
            "username": user.username,
            "started": datetime.now(timezone.utc).isoformat(),
        }
        save_bot_state(state)
        await monitor_with_bot(userbot, user, notifier, interval=interval)
        return

    # Scan lengkap
    await scan_and_export(userbot, user, msg_limit, notifier=notifier,
                          max_scan=max_scan, download=download, max_mb=max_mb)

    cprint("\n  ══ SELESAI ══", RED, attrs=["bold"])
    cprint("  Red Phantom · Stay sharp, stay red.\n", BRIGHT_RED)


# ══════════════════════════════════════════════════════════════════
# ENTRY
# ══════════════════════════════════════════════════════════════════
async def main():
    banner()

    # Cek konfigurasi bot
    if BOT_CONFIG["bot_token"] == "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ":
        error("GANTI BOT_CONFIG['bot_token'] dulu dengan token dari @BotFather!")
        error("GANTI BOT_CONFIG['admin_ids'] dengan ID Anda dari @userinfobot!")
        sys.exit(1)
    if not BOT_CONFIG["admin_ids"] or BOT_CONFIG["admin_ids"][0] == 123456789:
        error("GANTI BOT_CONFIG['admin_ids'] dengan ID Telegram Anda!")
        sys.exit(1)

    config = get_config()

    # Userbot (akun Anda)
    userbot = Client(
        config["session_name"],
        api_id=int(config["api_id"]),
        api_hash=config["api_hash"],
    )

    # Bot
    bot = Client(
        "red_phantom_bot",
        api_id=int(config["api_id"]),
        api_hash=config["api_hash"],
        bot_token=BOT_CONFIG["bot_token"],
    )

    notifier = BotNotifier(bot, BOT_CONFIG["admin_ids"])

    # Start both
    await userbot.start()
    await bot.start()

    me_bot = await bot.get_me()
    me_user = await userbot.get_me()
    success(f"Bot online: @{me_bot.username}")
    success(f"Userbot online: @{me_user.username or me_user.id}")
    info(f"Admin ID: {BOT_CONFIG['admin_ids']}")

    # Register bot handlers
    register_bot_handlers(bot, userbot, notifier)

    # Kirim welcome ke admin
    if BOT_CONFIG.get("notify_realtime", True):
        await notifier.send_text(
            f"🩸 **RED PHANTOM ONLINE**\n\n"
            f"Bot: `@{me_bot.username}`\n"
            f"Userbot: `@{me_user.username or me_user.id}`\n"
            f"Time: `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`\n\n"
            f"Ketik `/help` untuk commands."
        )

    # Menu interaktif CLI + Bot bersamaan
    try:
        while True:
            section("Menu Utama", "◆")
            print(colored("    1. Scan target (manual input)", BRIGHT_RED))
            print(colored("    2. Monitor target", BRIGHT_RED))
            print(colored("    3. Keluar", BRIGHT_RED))
            print(colored("\n    💡 Bot commands aktif — bisa juga kirim /scan via bot", "cyan"))

            choice = ask("Pilihan (1-3)", default="1")
            if choice == "3":
                break
            elif choice == "1":
                await run_manual(userbot, notifier)
            elif choice == "2":
                # Monitor
                user = await resolve_target(userbot)
                if user:
                    interval = ask_int("Interval detik", default=60, min_val=10)
                    state = load_bot_state()
                    state.setdefault("monitors", {})[str(user.id)] = {
                        "username": user.username,
                        "started": datetime.now(timezone.utc).isoformat(),
                    }
                    save_bot_state(state)
                    await notifier.send_text(f"🔴 Monitor started `@{user.username or user.id}`")
                    await monitor_with_bot(userbot, user, notifier, interval=interval)

    except KeyboardInterrupt:
        cprint("\n  [!] Dibatalkan.", "yellow")

    await notifier.send_text("⏹ **RED PHANTOM OFFLINE**")
    await bot.stop()
    await userbot.stop()
    cprint("\n  ══ BYE ══\n", RED, attrs=["bold"])


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
        import traceback
        traceback.print_exc()
        cprint(f"\n  [FATAL] {e}\n", RED, attrs=["bold"])
        sys.exit(1)
