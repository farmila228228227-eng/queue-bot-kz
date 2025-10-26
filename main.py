#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Queue Bot for Telegram (KZ-only, multi-chat, topics, active-number per user)
✅ Работает 24/7 на Replit
✅ Без aiogram, без imghdr — только requests + Flask
✅ С поддержкой UptimeRobot (anti-sleep)
"""

import os, json, time, requests
from flask import Flask
from threading import Thread

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN") or "ВСТАВЬ_СВОЙ_ТОКЕН_СЮДА"
OWNER_ID = 7322925570
DATA_FILE = "queue_data_kz_active.json"
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ========== ХРАНИЛИЩЕ ==========
if not os.path.exists(DATA_FILE):
    data = {
        "queue": {},
        "vips": [],
        "allowed_topics": {},
        "work_enabled": {},
        "active_numbers": {}
    }
    json.dump(data, open(DATA_FILE, "w"), ensure_ascii=False, indent=2)
else:
    data = json.load(open(DATA_FILE, "r", encoding="utf-8"))

def save():
    json.dump(data, open(DATA_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# ========== УТИЛИТЫ ==========
def api_post(method, payload):
    try:
        return requests.post(f"{API}/{method}", json=payload, timeout=15).json()
    except Exception as e:
        print("api_post error:", e)
        return None

def api_get(method, params):
    try:
        return requests.get(f"{API}/{method}", params=params, timeout=15).json()
    except Exception as e:
        print("api_get error:", e)
        return None

def send(chat_id, text, thread_id=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    try:
        api_post("sendMessage", payload)
    except Exception as e:
        print("send error:", e)

def mask(num):
    return num[:4] + "***" + num[-4:] if len(num) > 8 else "***"

def is_kz_number(num):
    n = num.replace(" ", "").replace("-", "")
    return n.startswith("+77") or n.startswith("77")

def chat_key(cid): return str(cid)
def get_tid(msg): return msg.get("message_thread_id", 0)

def is_admin(uid, cid):
    if uid == OWNER_ID: return True
    try:
        res = api_get("getChatMember", {"chat_id": cid, "user_id": uid})
        return res.get("result", {}).get("status") in ("administrator", "creator")
    except:
        return False

# ========== ЛОКАЛЬНЫЕ ФУНКЦИИ ==========
def get_queue(cid): return data.setdefault("queue", {}).setdefault(chat_key(cid), [])
def add_to_queue(cid, e): data["queue"][chat_key(cid)].append(e); save()
def pop_from_queue(cid):
    q = get_queue(cid)
    return q.pop(0) if q else None
def get_active_map(cid): return data.setdefault("active_numbers", {}).setdefault(chat_key(cid), {})
def set_active(cid, uid, e): data["active_numbers"][chat_key(cid)][str(uid)] = e; save()
def get_active(cid, uid): return data["active_numbers"].get(chat_key(cid), {}).get(str(uid))
def pop_active(cid, uid): return data["active_numbers"].get(chat_key(cid), {}).pop(str(uid), None)
def is_allowed(cid, tid): return tid in data.get("allowed_topics", {}).get(chat_key(cid), [])
def allow_topic(cid, tid): 
    arr = set(data.get("allowed_topics", {}).get(chat_key(cid), []))
    arr.add(tid); data["allowed_topics"][chat_key(cid)] = list(arr); save()
def unset_topic(cid, tid):
    arr = set(data.get("allowed_topics", {}).get(chat_key(cid), []))
    if tid in arr: arr.remove(tid)
    data["allowed_topics"][chat_key(cid)] = list(arr); save()
def is_work(cid, tid): return data.get("work_enabled", {}).get(chat_key(cid), {}).get(str(tid), False)
def set_work(cid, tid, s): data.setdefault("work_enabled", {}).setdefault(chat_key(cid), {})[str(tid)] = bool(s); save()

# ========== КОМАНДЫ ==========
def cmd_start(cid, tid): send(cid, "<b>✅ Бот запущен и готов к работе.</b>", tid)

def cmd_set(user, cid, tid):
    if user["id"] != OWNER_ID and not is_admin(user["id"], cid):
        send(cid, "<b>❌ Только владелец или админ могут использовать /set.</b>", tid)
        return
    allow_topic(cid, tid)
    send(cid, f"<b>✅ Топик {tid} разрешён для работы.</b>", tid)

def cmd_unset(user, cid, tid):
    if user["id"] != OWNER_ID and not is_admin(user["id"], cid):
        send(cid, "<b>❌ Только владелец или админ могут использовать /unset.</b>", tid)
        return
    unset_topic(cid, tid)
    send(cid, f"<b>🗑️ Топик {tid} удалён из разрешённых.</b>", tid)

def cmd_startwork(user, cid, tid):
    if user["id"] != OWNER_ID and not is_admin(user["id"], cid):
        send(cid, "<b>❌ Только админ может включить приём номеров.</b>", tid)
        return
    if not is_allowed(cid, tid):
        send(cid, "<b>❗ Сначала разрешите топик через /set.</b>", tid)
        return
    set_work(cid, tid, True)
    send(cid, "<b>✅ Приём номеров включён.</b>", tid)

def cmd_stopwork(user, cid, tid):
    if user["id"] != OWNER_ID and not is_admin(user["id"], cid):
        send(cid, "<b>❌ Только админ может выключить приём номеров.</b>", tid)
        return
    set_work(cid, tid, False)
    send(cid, "<b>⏸ Приём номеров выключен.</b>", tid)

def cmd_dn(user, text, cid, tid):
    if not is_allowed(cid, tid):
        send(cid, "<b>❗ Этот топик не разрешён. Используйте /set.</b>", tid); return
    if not is_work(cid, tid):
        send(cid, "<b>⏸ Приём номеров выключен. /startwork чтобы включить.</b>", tid); return
    lines = text.splitlines()[1:]; added = []
    for raw in lines:
        s = raw.strip()
        if is_kz_number(s):
            e = {"number": s, "user_id": user["id"], "username": user.get("username", ""), "ts": int(time.time())}
            add_to_queue(cid, e); added.append(s)
    if added:
        send(cid, "<b>✅ Добавлены номера:</b>\n" + "\n".join(f"<b>{mask(n)}</b>" for n in added), tid)
    else:
        send(cid, "<b>⚠️ Только номера KZ (+77...)</b>", tid)

def cmd_queue(cid, tid):
    q = get_queue(cid)
    if not q: send(cid, "<b>Очередь пуста.</b>", tid); return
    msg = [f"<b>Очередь ({len(q)}):</b>"]
    for e in q: msg.append(f"<b>{mask(e['number'])}</b> @{e['username']}")
    send(cid, "\n".join(msg), tid)

def cmd_nomer(user, cid, tid):
    if user["id"] != OWNER_ID and user["id"] not in data["vips"] and not is_admin(user["id"], cid):
        send(cid, "<b>❌ Нет прав на взятие номера.</b>", tid); return
    if get_active(cid, user["id"]):
        send(cid, "<b>⚠️ У вас уже есть активный номер. Сначала /skip.</b>", tid); return
    e = pop_from_queue(cid)
    if not e: send(cid, "<b>Очередь пуста.</b>", tid); return
    set_active(cid, user["id"], e)
    send(cid, f"<b>📤 Выдан номер:</b> {mask(e['number'])}\n<b>От:</b> @{e['username']}", tid)
    try: send(user["id"], f"<b>Ваш номер:</b> {e['number']}"); except: pass

def cmd_skip(user, cid, tid):
    a = get_active(cid, user["id"])
    if not a: send(cid, "<b>❗ У вас нет активного номера.</b>", tid); return
    pop_active(cid, user["id"])
    send(cid, f"<b>⏭ Скипнут номер:</b> {mask(a['number'])}", tid)

def cmd_addvbiv(user, cid, tid, args):
    if user["id"] != OWNER_ID and not is_admin(user["id"], cid):
        send(cid, "<b>❌ Только админ может добавить уполномоченного.</b>", tid); return
    if not args: send(cid, "<b>Использование: /addvbiv user_id</b>", tid); return
    try: target = int(args[0]); data["vips"].append(target); save()
    except: send(cid, "<b>Ошибка: неверный ID.</b>", tid); return
    send(cid, f"<b>✅ {target} добавлен в уполномоченные.</b>", tid)

# ========== ЦИКЛ ==========
def get_updates(offset=None):
    p = {"timeout": 30}
    if offset: p["offset"] = offset
    return api_get("getUpdates", p) or {}

def bot_loop():
    print("✅ Бот запущен (Replit 24/7).")
    offset = None
    while True:
        try:
            res = get_updates(offset)
            updates = res.get("result", [])
            for u in updates:
                offset = u["update_id"] + 1
                m = u.get("message"); 
                if not m: continue
                txt = (m.get("text") or "").strip()
                if not txt.startswith("/"): continue
                parts = txt.split(); cmd = parts[0].lower(); args = parts[1:]
                cid = m["chat"]["id"]; tid = get_tid(m); user = m["from"]
                if cmd == "/start": cmd_start(cid, tid)
                elif cmd == "/set": cmd_set(user, cid, tid)
                elif cmd == "/unset": cmd_unset(user, cid, tid)
                elif cmd == "/startwork": cmd_startwork(user, cid, tid)
                elif cmd == "/stopwork": cmd_stopwork(user, cid, tid)
                elif cmd == "/dn": cmd_dn(user, txt, cid, tid)
                elif cmd == "/queue": cmd_queue(cid, tid)
                elif cmd == "/nomer": cmd_nomer(user, cid, tid)
                elif cmd == "/skip": cmd_skip(user, cid, tid)
                elif cmd == "/addvbiv": cmd_addvbiv(user, cid, tid, args)
                else: send(cid, "<b>Неизвестная команда.</b>", tid)
        except Exception as e:
            print("Ошибка:", e); time.sleep(3)

# ========== FLASK WEB SERVER (для UptimeRobot) ==========
app = Flask('')

@app.route('/')
def home():
    return "✅ Telegram Queue Bot is running."

def run_web():
    app.run(host='0.0.0.0', port=8080)

def run_bot():
    bot_loop()

Thread(target=run_web).start()
Thread(target=run_bot).start()
