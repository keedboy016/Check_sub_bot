import asyncio
from telethon import TelegramClient
from pyrogram import Client as Pyro
from config import BOT_TOKEN, API_ID, API_HASH
import bot

async def main():
    # pyrogram для отправки больших файлов
    pyro = Pyro("pyro_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    await pyro.start()
    bot.set_pyro(pyro)

    # telethon для приёма
    tele = TelegramClient("tele_bot", API_ID, API_HASH)
    await tele.start(bot_token=BOT_TOKEN)
    bot.register(tele)

    print("бот работает")
    await tele.run_until_disconnected()

asyncio.run(main())
