import json, os
from datetime import datetime
from config import DB_FILE

def load():
    if not os.path.exists(DB_FILE):
        _w({"groups": {}, "builds": {}, "builders": [], "stats": {"users": {}, "dls": {}, "total": 0}})
    return json.load(open(DB_FILE, encoding="utf-8"))

def _w(d):
    json.dump(d, open(DB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def groups():   return load()["groups"]
def builds():   return load()["builds"]
def builders(): return load().get("builders", [])

def add_group(key, label, chs, owner=None):
    d = load(); d["groups"][key] = {"channels": chs, "label": label, "owner": owner}; _w(d)

def del_group(key):
    d = load(); d["groups"].pop(key, None); _w(d)

def add_build(key, desc, msg_id, chat_id, size, uid):
    d = load()
    d["builds"][key] = {"desc": desc, "msg_id": msg_id, "chat_id": chat_id,
                        "size": size, "by": uid, "at": datetime.now().isoformat()}
    d["stats"]["dls"].setdefault(key, 0); _w(d)

def del_build(key):
    d = load(); d["builds"].pop(key, None); d["stats"]["dls"].pop(key, None); _w(d)

def add_builder(uid):
    d = load()
    if uid not in d["builders"]: d["builders"].append(uid)
    _w(d)

def del_builder(uid):
    d = load()
    try: d["builders"].remove(uid)
    except: pass
    _w(d)

# трекаем пользователя
def track(uid, uname=None, name=None):
    d = load(); k = str(uid); now = datetime.now().isoformat()
    if k not in d["stats"]["users"]:
        d["stats"]["users"][k] = {"uname": uname, "name": name, "first": now, "last": now, "dls": [], "req": 1}
        d["stats"]["total"] = len(d["stats"]["users"])
    else:
        u = d["stats"]["users"][k]; u["last"] = now
        if uname: u["uname"] = uname
        if name:  u["name"]  = name
        u["req"] = u.get("req", 0) + 1
    _w(d)

def track_dl(uid, key):
    d = load(); k = str(uid)
    d["stats"]["dls"][key] = d["stats"]["dls"].get(key, 0) + 1
    if k in d["stats"]["users"]:
        d["stats"]["users"][k].setdefault("dls", []).append({"key": key, "at": datetime.now().isoformat()})
    _w(d)

def stats(): return load()["stats"]

def banned(): return load().get("banned", [])

def ban_user(uid):
    d = load(); d.setdefault("banned", [])
    if uid not in d["banned"]: d["banned"].append(uid)
    _w(d)

def unban_user(uid):
    d = load(); d.setdefault("banned", [])
    try: d["banned"].remove(uid)
    except: pass
    _w(d)
