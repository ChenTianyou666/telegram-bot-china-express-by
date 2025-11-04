import os
import asyncio
import re
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BotCommand
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv
import time

# ===================== 日志配置 =====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ===================== 配置 =====================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # 例: https://chinaexpressby.com/
PORT = int(os.getenv("PORT", 8000))

if not BOT_TOKEN or not WEBHOOK_URL:
    logging.error("❌ BOT_TOKEN or WEBHOOK_URL not found in .env")
    raise ValueError("BOT_TOKEN or WEBHOOK_URL missing!")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

os.makedirs("photos", exist_ok=True)
user_state = {}

# ===================== 商品类别 =====================
categories = [
    "Кроссовки/Туфли/Кеды", "Детская обувь", "Сланцы/Тапки/Кроксы",
    "Куртка (зима)", "Куртка (осень/весна)", "Кофта/Байка",
    "Штаны", "Шорты", "Головной убор", "Бижутерия",
    "Ремни", "Сумка женская", "Рюкзак", "Большая дорожная сумка"
]
category_weights = [2.3,1.35,1.17,3.6,2.3,1.4,1.7,1.1,0.68,0.4,0.9,1.32,1.9,2.49]

# ===================== 主菜单按钮 =====================
main_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Рассчитать", callback_data="menu_calculate")],
        [InlineKeyboardButton(text="Менеджер", url="https://t.me/yun_swthrt")],
        [InlineKeyboardButton(text="Отзывы", url="https://t.me/chexby_otzyv")],
        [InlineKeyboardButton(text="Инструкция", callback_data="menu_instruction")]
    ]
)

# ===================== 设置 /start 命令 =====================
async def set_bot_commands():
    commands = [BotCommand(command="start", description="Запуск бота")]
    await bot.set_my_commands(commands)

async def send_welcome(user_id: int):
    photo_path = "touxiang.jpg"
    start_text = "Добро пожаловать в официальный чат-бот 📌<b>China Express BY</b> 📌👇\nВыберите нужный вам пункт:"
    try:
        if os.path.exists(photo_path):
            await bot.send_photo(user_id, FSInputFile(photo_path), caption=start_text)
        else:
            await bot.send_message(user_id, start_text)
        await bot.send_message(user_id, "Выберите действие:", reply_markup=main_keyboard)
    except Exception as e:
        logging.error(f"send_welcome error: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_state.pop(message.from_user.id, None)
    logging.info(f"User {message.from_user.id} started the bot")
    await send_welcome(message.from_user.id)

# ===================== Инструкция =====================
@dp.callback_query(lambda c: c.data == "menu_instruction")
async def menu_instruction(callback: types.CallbackQuery):
    text = (
        "Инструкция по чат-боту ✅\n\n"
        "1. Нажмите Старт\n"
        "2. Нажмите Рассчитать стоимость\n"
        "3. Выберите категорию товара\n"
        "4. Отправьте ссылку, размер, цену\n\n"
        "Бот рассчитает стоимость с доставкой ✅"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Менеджер", url="https://t.me/yun_swthrt")],
            [InlineKeyboardButton(text="Рассчитать", callback_data="menu_calculate")]
        ]
    )
    await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()

# ===================== Рассчитать =====================
@dp.callback_query(lambda c: c.data == "menu_calculate")
async def menu_calculate(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=cat, callback_data=f"category_{i}")] for i, cat in enumerate(categories)]
    )
    await callback.message.answer("Выберите категорию товара ⬇️", reply_markup=keyboard)
    await callback.answer()

# ===================== 选择类别 + 发送三张图片 =====================
@dp.callback_query(F.data.startswith("category_"))
async def category_selected(callback: types.CallbackQuery):
    index = int(callback.data.split("_")[1])
    user_state[callback.from_user.id] = {
        "category": categories[index],
        "weight": category_weights[index],
        "step": "waiting_link",
        "photo_file": None,
        "link": None
    }
    await callback.message.answer(
        f"✅ Категория выбрана: {categories[index]}\n"
        "📌 Отправьте ссылку на товар (желательно с фото)."
    )
    try:
        media = [
            types.InputMediaPhoto(media=FSInputFile("link1.jpg")),
            types.InputMediaPhoto(media=FSInputFile("link2.jpg")),
            types.InputMediaPhoto(media=FSInputFile("link3.jpg"))
        ]
        await bot.send_media_group(chat_id=callback.from_user.id, media=media)
    except Exception as e:
        logging.error(f"send_media_group error: {e}")
    await callback.answer()

# ===================== 处理照片 + 链接 =====================
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    uid = message.from_user.id
    state = user_state.get(uid)
    if not state or state["step"] != "waiting_link":
        return
    try:
        file_id = message.photo[-1].file_id
        file = await bot.get_file(file_id)
        path = f"photos/{uid}_{file_id}.jpg"
        await bot.download_file(file.file_path, path)
        state["photo_file"] = path

        if message.caption:
            link_match = re.search(r'https?://\S+', message.caption)
            if link_match:
                state["link"] = link_match.group(0)

        if state.get("link"):
            state["step"] = "waiting_size"
            await message.answer("Фото и ссылка получены ✅\nВведите размер товара:")
        else:
            await message.answer("Фото получено 📸\nПожалуйста, отправьте ссылку ✅")
    except Exception as e:
        logging.error(f"handle_photo error: {e}")

# ===================== 文本处理 =====================
@dp.message(F.text)
async def handle_text(message: types.Message):
    uid = message.from_user.id
    state = user_state.get(uid)
    if not state:
        return
    try:
        if state["step"] == "waiting_link":
            link_match = re.search(r'https?://\S+', message.text)
            if link_match:
                state["link"] = link_match.group(0)
                state["step"] = "waiting_size"
                await message.answer("Ссылка получена ✅\nВведите размер товара:")
            return

        if state["step"] == "waiting_size":
            state["size"] = message.text
            state["step"] = "waiting_price"
            await message.answer("Введите цену товара (¥ CNY):")
            return

        if state["step"] == "waiting_price":
            price = float(message.text.replace(",", "."))
            usd_total = (price / 6.8) * 1.331 + state["weight"]*7.5

            caption = (
                f"✅ Расчёт завершён\n\n"
                f"Категория: {state['category']}\n"
                f"Размер: {state['size']}\n"
                f"Цена: ¥{price:.2f}\n"
                f"Итого: {usd_total:.2f} $ USD (с доставкой)\n"
            )

            if state.get("link"):
                caption += f"Ссылка: {state['link']}\n\n"

            caption += "📩 Отправьте это сообщение менеджеру"

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Отправить менеджеру", url="https://t.me/yun_swthrt")]]
            )

            if state.get("photo_file"):
                await message.answer_photo(FSInputFile(state["photo_file"]), caption=caption, reply_markup=keyboard)
            else:
                await message.answer(caption, reply_markup=keyboard)

            user_state.pop(uid, None)
    except Exception as e:
       logging.error(f"handle_text error: {e}")


# ===================== 定时清理照片文件夹 =====================
async def cleanup_photos():
    while True:
        try:
            now = time.time()
            for filename in os.listdir("photos"):
                filepath = os.path.join("photos", filename)
                if os.path.isfile(filepath) and now - os.path.getmtime(filepath) > 24*3600:  # 24小时
                    os.remove(filepath)
                    logging.info(f"Deleted old photo: {filename}")
        except Exception as e:
            logging.error(f"cleanup_photos error: {e}")
        await asyncio.sleep(3600)

# ===================== Webhook 启动 =====================
async def on_startup(app):
    await set_bot_commands()
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL)
    asyncio.create_task(cleanup_photos())
    logging.info("✅ Bot started with webhook...")

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/")
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)

