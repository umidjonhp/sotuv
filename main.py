import logging
import asyncio
import sys
import time
import os
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- WINDOWS UCHUN ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- SOZLAMALAR ---
TOKEN = "7957158545:AAHUYgH1ijaiqgvYZhNnLUX4dvhEGI4NzcU" 
API_URL = "https://script.google.com/macros/s/AKfycbxFHfDjqz3sBFI8XIB30NkfLBv3ZmqD1SgLQqqn4QwKy7refC-v4-PdSM72Er3V2juf/exec"

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

# --- KESHLASH TIZIMI (TEZ ISHLASH UCHUN) ---
cache = {}
CACHE_TTL = 300  # 5 daqiqa davomida ma'lumotni xotirada saqlaydi

async def fetch_data(params):
    cache_key = str(params)
    now = time.time()
    
    if cache_key in cache:
        data, timestamp = cache[cache_key]
        if now - timestamp < CACHE_TTL:
            return data

    timeout = aiohttp.ClientTimeout(total=20)
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        try:
            async with session.get(API_URL, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    cache[cache_key] = (data, now)
                    return data
        except Exception as e:
            logging.error(f"Tarmoq xatosi: {e}")
            return cache.get(cache_key, (None, 0))[0]
    return None

# --- BOT LOGIKASI ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    data = await fetch_data({"action": "get_sheets"})
    if not data:
        return await message.answer("❌ Ma'lumot olib bo'lmadi. VPN ni tekshiring.")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🏢 {s}", callback_data=f"p_{s}")] for s in data
    ])
    await message.answer("🏠 <b>Suf Buildings</b>\nLoyihani tanlang:", reply_markup=kb)

# 1. Yo'laklarni chiqarish (Holati bilan)
@dp.callback_query(F.data.startswith("p_"))
async def show_sections(callback: CallbackQuery):
    sheet = callback.data.split("_")[1]
    data = await fetch_data({"sheet": sheet})
    if not data: return await callback.answer("Ma'lumot yuklanmoqda...")
    
    section_status = {}
    for i in data:
        sect = str(i.get('Padez', '1'))
        st = str(i.get('Holat', '')).lower()
        if sect not in section_status: section_status[sect] = False
        if any(x in st for x in ["bo'sh", "bosh", "sotuvda"]): section_status[sect] = True

    btns = [[InlineKeyboardButton(text=f"{'🟢' if section_status[s] else '🔴'} {s}-yo'lak", 
            callback_data=f"s_{sheet}_{s}")] for s in sorted(section_status.keys(), key=lambda x: int(x) if x.isdigit() else 0)]
    
    btns.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")])
    await callback.message.edit_text(f"🏢 <b>{sheet}</b>\nYo'lakni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

# 2. Qavatlarni chiqarish
@dp.callback_query(F.data.startswith("s_"))
async def show_floors(callback: CallbackQuery):
    _, sheet, sect = callback.data.split("_")
    data = await fetch_data({"sheet": sheet})
    if not data: return await callback.answer("Xato!")

    floors = {}
    for i in data:
        if str(i.get('Padez')) == sect:
            q = str(i.get('Qavat', '?'))
            st = str(i.get('Holat', '')).lower()
            if q not in floors: floors[q] = False
            if any(x in st for x in ["bo'sh", "bosh", "sotuvda"]): floors[q] = True

    btns, row = [], []
    for q in sorted(floors.keys(), key=lambda x: int(x) if x.isdigit() else 0, reverse=True):
        icon = "🟢" if floors[q] else "🔴"
        row.append(InlineKeyboardButton(text=f"{icon} {q}-qavat", callback_data=f"f_{sheet}_{sect}_{q}"))
        if len(row) == 2: btns.append(row); row = []
    if row: btns.append(row)
    
    btns.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"p_{sheet}")])
    await callback.message.edit_text(f"🏢 {sheet} | 🚪 {sect}-yo'lak\nQavatni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

# 3. Xonadonlarni chiqarish
@dp.callback_query(F.data.startswith("f_"))
async def show_units(callback: CallbackQuery):
    _, sheet, sect, qavat = callback.data.split("_")
    data = await fetch_data({"sheet": sheet})
    if not data: return await callback.answer("Xato!")
    
    btns, row = [], []
    for i in data:
        if str(i.get('Padez')) == sect and str(i.get('Qavat')) == qavat:
            st = str(i.get('Holat', '')).lower()
            n = str(i.get('Xonadon raqami', '?'))
            icon = "🟢" if any(x in st for x in ["bo'sh", "bosh", "sotuvda"]) else "🔴"
            row.append(InlineKeyboardButton(text=f"{icon} №{n}", callback_data=f"i_{sheet}_{n}"))
            if len(row) == 3: btns.append(row); row = []
    if row: btns.append(row)
    
    btns.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"s_{sheet}_{sect}")])
    await callback.message.edit_text(f"🏢 {sheet} | {sect}-yo'lak | {qavat}-qavat", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

# 4. To'liq ma'lumot
@dp.callback_query(F.data.startswith("i_"))
async def show_info(callback: CallbackQuery):
    _, sheet, nomer = callback.data.split("_")
    data = await fetch_data({"sheet": sheet})
    h = next((x for x in data if str(x.get('Xonadon raqami')) == str(nomer)), None)
    
    if h:
        msg = (f"🏠 <b>Xonadon №{h.get('Xonadon raqami', '-')}</b>\n"
               f"━━━━━━━━━━━━━\n"
               f"📐 Maydoni: {h.get('kv/m', '-')} m² | Xona: {h.get('Xona', '-')}\n"
               f"📊 Holati: {h.get('Holat', '-')} | Narxi: {h.get('Narx', '-')}\n"
               f"🛠 Remonti: {h.get('Remont', '-')}")
        await callback.message.answer(msg)
    await callback.answer()

@dp.callback_query(F.data == "back")
async def back_home(callback: CallbackQuery):
    await callback.message.delete()
    await cmd_start(callback.message)

# --- SERVER QISMI (RENDER UCHUN) ---
async def handle(request): return web.Response(text="Bot is running")

async def main():
    # Web server 8080 portda ishlaydi
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080))).start()
    
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except:
        pass