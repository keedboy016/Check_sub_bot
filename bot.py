from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import ChannelParticipantBanned, ChannelParticipantLeft
from datetime import datetime
import storage as db
from config import ADMIN_ID, MAIN_CH

_pyro   = None
_states = {}  # состояния диалогов

def set_pyro(p): global _pyro; _pyro = p

# размер файла в читаемый вид
def fsize(b):
    if b < 1024**2: return f"{b/1024:.1f} KB"
    if b < 1024**3: return f"{b/1024**2:.1f} MB"
    return f"{b/1024**3:.2f} GB"

def is_admin(uid):   return uid == ADMIN_ID
def is_builder(uid): return uid in db.builders() or is_admin(uid)

# работа со стейтами
def ss(uid, step, **kw): _states[uid] = {"step": step, "data": kw}
def gs(uid):             return _states.get(uid, {})
def cs(uid):             _states.pop(uid, None)

# проверка подписки
async def subbed(client, uid, ch):
    try:
        r = await client(GetParticipantRequest(ch, uid))
        return not isinstance(r.participant, (ChannelParticipantBanned, ChannelParticipantLeft))
    except: return False

async def missing(client, uid, extra):
    return [c for c in [MAIN_CH] + extra if not await subbed(client, uid, c)]

# кнопки подписки
def sub_btns(chs):
    rows = [[Button.url(f"📢 {c}", f"https://t.me/{c.lstrip('@')}")] for c in chs]
    rows += [[Button.inline("✅ Я подписался", b"cs")]]
    return rows

# меню сборок
def builds_kb(only=None):
    bl = db.builds()
    if not bl: return [[Button.inline("😕 Сборок нет", b"noop")]]
    if only:
        b = bl.get(only)
        return [[Button.inline(f"⬇️ {b['desc'][:45]}", f"dl_{only}".encode())]] if b else [[Button.inline("❌ Не найдено", b"noop")]]
    return [[Button.inline(f"📦 {v['desc'][:45]}", f"dl_{k}".encode())] for k, v in bl.items()]

# -- клавиатуры --
def adm_main():
    return [[Button.inline("🔗 Группы/ссылки",  b"ag")],
            [Button.inline("📦 Сборки",          b"ab")],
            [Button.inline("👷 Сборщики",        b"abl")],
            [Button.inline("📊 Статистика",      b"ast")],
            [Button.inline("❌ Закрыть",         b"acl")]]

def adm_groups():
    rows = [[Button.inline(f"🗑 {v['label']} [{k}]", f"gd_{k}".encode())] for k, v in db.groups().items()]
    rows += [[Button.inline("➕ Создать", b"ga")], [Button.inline("📋 Список", b"gls")], [Button.inline("◀️ Назад", b"amn")]]
    return rows

def adm_builds():
    rows = [[Button.inline(f"🗑 {v['desc'][:35]} [{k}]", f"bd_{k}".encode())] for k, v in db.builds().items()]
    rows += [[Button.inline("➕ Добавить", b"ba")], [Button.inline("◀️ Назад", b"amn")]]
    return rows

def adm_bldrs():
    rows = [[Button.inline(f"🗑 {uid}", f"bld_{uid}".encode())] for uid in db.builders()]
    rows += [[Button.inline("➕ Добавить", b"bla")], [Button.inline("◀️ Назад", b"amn")]]
    return rows

def bldr_main():
    return [[Button.inline("🔗 Создать ссылку на сборку", b"bm_lnk")],
            [Button.inline("📤 Залить свою сборку",       b"bm_up")]]

def bldr_pick():
    bl = db.builds()
    rows = [[Button.inline(f"📦 {v['desc'][:45]}", f"bpk_{k}".encode())] for k, v in bl.items()]
    rows += [[Button.inline("◀️ Назад", b"bmb")]]
    return rows

# статистика — собираем текст
def stat_text():
    s  = db.stats(); users = s["users"]; dls = s["dls"]; bl = db.builds(); now = datetime.now()
    def days_ago(iso, n): return (now - datetime.fromisoformat(iso)).days <= n

    today  = lambda x: x[:10] == now.strftime("%Y-%m-%d")
    active = lambda n: sum(1 for u in users.values() if u.get("last") and days_ago(u["last"], n))
    new    = lambda n: sum(1 for u in users.values() if u.get("first") and days_ago(u["first"], n))

    top = sorted(dls.items(), key=lambda x: x[1], reverse=True)[:5]
    top_lines = [f"  • {bl.get(k,{}).get('desc','?')[:30]} — {cnt}" for k, cnt in top]
    all_lines = [f"  {bl.get(k,{}).get('desc','?')[:28]} [{k}] — {cnt} шт / {fsize(bl.get(k,{}).get('size',0))}"
                 for k, cnt in sorted(dls.items(), key=lambda x: x[1], reverse=True)]

    return "\n".join([
        "📊 **Статистика**\n",
        "👥 **Пользователи**",
        f"  Всего: {s.get('total',0)}",
        f"  Активны сегодня: {active(0)}",
        f"  За 7 дней: {active(7)}",
        f"  За 30 дней: {active(30)}",
        f"  Новых сегодня: {sum(1 for u in users.values() if today(u.get('first','')))}",
        f"  Новых за неделю: {new(7)}", "",
        "⬇️ **Скачивания**",
        f"  Всего: {sum(dls.values())}", "",
        "🏆 **Топ 5:**", *top_lines, "",
        "📦 **Все сборки:**", *all_lines, "",
        f"👷 Сборщиков: {len(db.builders())}",
        f"🔗 Групп: {len(db.groups())}",
        f"🕐 {now.strftime('%d.%m.%Y %H:%M')}",
    ])

# отправка файла через pyrogram
async def send_file(uid, key):
    b = db.builds().get(key)
    if not b or not _pyro: return False
    try:
        await _pyro.forward_messages(chat_id=uid, from_chat_id=b["chat_id"], message_ids=b["msg_id"])
        db.track_dl(uid, key); return True
    except Exception as e:
        print(f"pyro send err: {e}"); return False

def register(client: TelegramClient):

    @client.on(events.NewMessage(pattern="/start", incoming=True, func=lambda e: e.is_private))
    async def start(event):
        uid  = event.sender_id
        u    = await event.get_sender()
        db.track(uid, getattr(u, "username", None), getattr(u, "first_name", None))
        cs(uid)

        args    = event.message.text.split(None, 1)
        payload = args[1].strip() if len(args) > 1 else ""

        if is_admin(uid):
            await event.respond("🛠 **Админка**", buttons=adm_main()); return
        if is_builder(uid):
            await event.respond("👷 **Меню сборщика**", buttons=bldr_main()); return

        # парсим payload — либо группа, либо ссылка сборщика
        target, extra = None, []
        if payload.startswith("bld_"):
            parts = payload[4:].split("_", 1)
            if len(parts) == 2:
                ch_raw, target = parts
                extra = [f"@{ch_raw}" if not ch_raw.startswith("@") else ch_raw]
        elif payload:
            extra = db.groups().get(payload, {}).get("channels", [])

        _states[uid] = {"step": None, "data": {"payload": payload, "extra": extra, "target": target}}
        miss = await missing(client, uid, extra)
        if miss:
            await event.respond("👋 Подпишись чтобы получить сборки 👇", buttons=sub_btns(miss))
        else:
            await event.respond("✅ Выбирай сборку 👇", buttons=builds_kb(target))

    @client.on(events.NewMessage(pattern="/admin", incoming=True, func=lambda e: e.is_private))
    async def admin_cmd(event):
        if not is_admin(event.sender_id): await event.respond("⛔ нет доступа"); return
        cs(event.sender_id)
        await event.respond("🛠 **Админка**", buttons=adm_main())

    @client.on(events.NewMessage(pattern="/builder", incoming=True, func=lambda e: e.is_private))
    async def builder_cmd(event):
        uid = event.sender_id
        if not is_builder(uid): await event.respond("⛔ нет статуса"); return
        cs(uid); await event.respond("👷 **Меню сборщика**", buttons=bldr_main())

    @client.on(events.NewMessage(pattern="/id", incoming=True, func=lambda e: e.is_private))
    async def id_cmd(event):
        await event.respond(f"`{event.sender_id}`", parse_mode="markdown")

    @client.on(events.CallbackQuery)
    async def cb(event):
        uid  = event.sender_id
        d    = event.data.decode()

        if d == "noop": await event.answer(); return

        # проверка подписки после нажатия
        if d == "cs":
            await event.answer()
            st   = gs(uid).get("data", {})
            miss = await missing(client, uid, st.get("extra", []))
            if miss: await event.edit("❌ Ещё не подписан:", buttons=sub_btns(miss))
            else:    await event.edit("✅ Выбирай сборку 👇", buttons=builds_kb(st.get("target")))
            return

        # скачать сборку
        if d.startswith("dl_"):
            key = d[3:]
            if not db.builds().get(key): await event.answer("❌ нет такой", alert=True); return
            await event.answer("📤 Отправляю...")
            if not await send_file(uid, key):
                await client.send_message(uid, "❌ Ошибка. Напиши администратору.")
            return

        # всё что ниже — только билдеры и админ
        if not (is_admin(uid) or is_builder(uid)):
            await event.answer("⛔", alert=True); return

        cbs = {
            "amn":  lambda: event.edit("🛠 **Админка**", buttons=adm_main()),
            "ag":   lambda: event.edit(f"🔗 Групп: {len(db.groups())}", buttons=adm_groups()),
            "ab":   lambda: event.edit(f"📦 Сборок: {len(db.builds())}", buttons=adm_builds()),
            "acl":  lambda: event.delete(),
            "bmb":  lambda: event.edit("👷 **Меню сборщика**", buttons=bldr_main()),
            "bm_lnk": lambda: event.edit("📦 Выбери сборку:", buttons=bldr_pick()) if db.builds() else event.answer("сборок нет", alert=True),
            "bm_up":  lambda: (ss(uid, "up_desc", msg_id=event.message_id),
                               event.edit("📝 Введи описание сборки:", buttons=[[Button.inline("❌ Отмена", b"cancel")]])),
        }

        if d in cbs:
            await event.answer()
            r = cbs[d]()
            if hasattr(r, "__await__"): await r
            return

        # статистика
        if d == "ast":
            if not is_admin(uid): await event.answer("⛔", alert=True); return
            await event.answer()
            await event.edit(stat_text(), parse_mode="markdown",
                             buttons=[[Button.inline("🔄", b"ast"), Button.inline("◀️", b"amn")]])

        elif d == "abl":
            if not is_admin(uid): await event.answer("⛔", alert=True); return
            await event.answer()
            await event.edit(f"👷 Сборщиков: {len(db.builders())}", buttons=adm_bldrs())

        elif d == "gls":
            await event.answer()
            bot_info = await client.get_me()
            g = db.groups()
            if not g: txt = "😕 Групп нет"
            else:
                lines = [f"**{v['label']}** `{k}`\n`https://t.me/{bot_info.username}?start={k}`\n{', '.join(v['channels'])}\n"
                         for k, v in g.items()]
                txt = "📋 **Ссылки:**\n\n" + "\n".join(lines)
            await event.edit(txt, parse_mode="markdown", buttons=[[Button.inline("◀️", b"ag")]])

        elif d == "ga":
            await event.answer()
            ss(uid, "grp_key", msg_id=event.message_id)
            await event.edit("🔑 Ключ группы (лат/цифры/_):", buttons=[[Button.inline("❌ Отмена", b"cancel")]])

        elif d == "ba":
            await event.answer()
            ss(uid, "bld_key", msg_id=event.message_id)
            await event.edit("🔑 Ключ сборки (лат/цифры/_):", buttons=[[Button.inline("❌ Отмена", b"cancel")]])

        elif d == "bla":
            if not is_admin(uid): await event.answer("⛔", alert=True); return
            await event.answer()
            ss(uid, "add_bdr", msg_id=event.message_id)
            await event.edit("Введи Telegram ID нового сборщика:", buttons=[[Button.inline("❌ Отмена", b"cancel")]])

        elif d.startswith("gd_"):
            await event.answer()
            key = d[3:]; label = db.groups().get(key, {}).get("label", key)
            db.del_group(key)
            await event.edit(f"🗑 `{label}` удалена", parse_mode="markdown",
                             buttons=[[Button.inline("◀️", b"ag")]])

        elif d.startswith("bd_"):
            await event.answer()
            key = d[3:]; desc = db.builds().get(key, {}).get("desc", key)
            db.del_build(key)
            await event.edit(f"🗑 `{desc[:40]}` удалена", parse_mode="markdown",
                             buttons=[[Button.inline("◀️", b"ab")]])

        elif d.startswith("bld_") and d != "bld_key":
            if not is_admin(uid): await event.answer("⛔", alert=True); return
            await event.answer()
            tid = int(d[4:]); db.del_builder(tid)
            await event.edit(f"🗑 {tid} убран", buttons=[[Button.inline("◀️", b"abl")]])

        elif d.startswith("bpk_"):
            await event.answer()
            key = d[4:]
            ss(uid, "bldr_ch", build_key=key, msg_id=event.message_id)
            desc = db.builds().get(key, {}).get("desc", "")
            await event.edit(f"✅ Сборка: `{desc[:45]}`\n\nВведи @username твоего канала:",
                             parse_mode="markdown", buttons=[[Button.inline("❌ Отмена", b"cancel")]])

        elif d == "cancel":
            cs(uid)
            await event.answer()
            if is_admin(uid): await event.edit("🛠 **Админка**", buttons=adm_main())
            else:             await event.edit("👷 **Меню сборщика**", buttons=bldr_main())

    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and e.text and not e.text.startswith("/")))
    async def on_text(event):
        uid  = event.sender_id
        st   = gs(uid); step = st.get("step")
        if not step: return
        data = st.get("data", {}); text = event.message.text.strip()

        async def upd(msg, btns):
            try: await client.edit_message(uid, data["msg_id"], msg, buttons=btns, parse_mode="markdown")
            except: pass

        cancel_btn = [[Button.inline("❌ Отмена", b"cancel")]]

        if step == "grp_key":
            await event.delete()
            if not text.replace("_","").isalnum(): await upd("❌ Только лат/цифры/_", cancel_btn); return
            if text in db.groups():               await upd(f"❌ `{text}` занят",     cancel_btn); return
            ss(uid, "grp_label", msg_id=data["msg_id"], key=text)
            await upd(f"✅ Ключ: `{text}`\n\nНазвание группы:", cancel_btn)

        elif step == "grp_label":
            await event.delete()
            ss(uid, "grp_chs", msg_id=data["msg_id"], key=data["key"], label=text)
            await upd(f"✅ `{data['key']}` / `{text}`\n\nКаналы через запятую:\n`@ch1, @ch2`\n📌 @pweper авто", cancel_btn)

        elif step == "grp_chs":
            await event.delete()
            chs = [c.strip() for c in text.replace("\n",",").split(",") if c.strip()]
            chs = [c if c.startswith("@") else f"@{c}" for c in chs]
            db.add_group(data["key"], data["label"], chs, owner=uid if not is_admin(uid) else None)
            bot_info = await client.get_me()
            link = f"https://t.me/{bot_info.username}?start={data['key']}"
            cs(uid)
            await upd(f"🎉 Группа создана!\n\n🔑 `{data['key']}`\n📝 `{data['label']}`\n"
                      f"📢 {', '.join(chs)}\n\n🔗 `{link}`",
                      [[Button.inline("◀️ Группы", b"ag"), Button.inline("🏠 Меню", b"amn")]])

        elif step == "bld_key":
            await event.delete()
            if not text.replace("_","").isalnum(): await upd("❌ Только лат/цифры/_", cancel_btn); return
            if text in db.builds():               await upd(f"❌ `{text}` занят",     cancel_btn); return
            ss(uid, "bld_desc", msg_id=data["msg_id"], key=text)
            await upd(f"✅ Ключ: `{text}`\n\nОписание сборки (пользователи это увидят):", cancel_btn)

        elif step == "bld_desc":
            await event.delete()
            ss(uid, "bld_file", msg_id=data["msg_id"], key=data["key"], desc=text)
            await upd(f"✅ `{data['key']}` / `{text}`\n\nОтправь ZIP-файл 👇", cancel_btn)

        elif step == "add_bdr":
            await event.delete()
            try:   tid = int(text)
            except: await upd("❌ Нужен числовой ID", cancel_btn); return
            db.add_builder(tid); cs(uid)
            await upd(f"✅ {tid} теперь сборщик\nПусть напишет /builder",
                      [[Button.inline("◀️ Сборщики", b"abl"), Button.inline("🏠", b"amn")]])

        elif step == "bldr_ch":
            await event.delete()
            ch = text if text.startswith("@") else f"@{text}"
            bot_info = await client.get_me(); key = data["build_key"]
            desc = db.builds().get(key, {}).get("desc", "")
            link = f"https://t.me/{bot_info.username}?start=bld_{ch.lstrip('@')}_{key}"
            cs(uid)
            await upd(f"🎉 Ссылка готова!\n\n📦 `{desc[:45]}`\n📢 {ch} + @pweper\n\n🔗 `{link}`",
                      [[Button.inline("◀️ Меню", b"bmb")]])

        elif step == "up_desc":
            await event.delete()
            ss(uid, "up_file", msg_id=data["msg_id"], desc=text)
            await upd(f"✅ Описание: `{text}`\n\nОтправь ZIP-файл 👇", cancel_btn)

    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and e.file is not None))
    async def on_file(event):
        uid  = event.sender_id
        st   = gs(uid); step = st.get("step")
        if step not in ("bld_file", "up_file"): return
        data = st.get("data", {}); f = event.file

        if not f.name or not f.name.lower().endswith(".zip"):
            await event.delete()
            await client.send_message(uid, "❌ Нужен .zip файл"); return

        key = data.get("key") or f"bld_{uid}_{int(datetime.now().timestamp())}"
        desc = data.get("desc", "без описания")

        db.add_build(key, desc, event.id, event.chat_id, f.size, uid)
        await event.delete(); cs(uid)

        try:
            await client.edit_message(uid, data["msg_id"],
                f"✅ Сборка добавлена!\n🔑 `{key}`\n📝 `{desc}`\n📦 {fsize(f.size)}",
                parse_mode="markdown",
                buttons=[[Button.inline("◀️ Сборки", b"ab"), Button.inline("🏠", b"amn")]])
        except:
            await client.send_message(uid, f"✅ `{desc}` добавлена | {fsize(f.size)}", parse_mode="markdown")
