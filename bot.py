import asyncio
import os
import uuid
import aiohttp
from datetime import datetime, timezone, timedelta
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PROCESS_URL = os.getenv("PROCESS_URL", "http://backend:8000/api/v1/zametki/process")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
aclient = AsyncOpenAI(api_key=os.getenv('AI_API_KEY'), base_url=os.getenv('AI_BASE_URL'))

# Настраиваем Московское время (UTC+3)
MSK = timezone(timedelta(hours=3), name="MSK")

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    greeting = (
        "Привет! Я твой умный AI-ассистент для заметок. Отправь мне текст или запиши голосовое сообщение.\n\n"
        "Что я умею:\n"
        "📝 Сохранять: просто напиши мысль, идею или факт.\n"
        "🏷 Авто-теги: сам проставлю теги (РАБОТА, ОТДЫХ, УЧЕБА, ХОББИ, БЫТОВУХА, СПИСКИ и др.).\n"
        "🔍 Искать по смыслу: 'покажи про спорт' или 'найди рецепт'.\n"
        "📚 Показывать всё: 'покажи все заметки'.\n"
        "⏰ Ставить таймеры: 'напомни завтра в 15:00 купить хлеб'.\n"
        "🔄 Повторять: 'напоминай пить воду каждые 3 часа' или 'потянуться через 10 секунд 3 раза'.\n"
        "📋 Показывать таймеры: 'какие есть таймеры'.\n"
        "🗑 Удалять: 'удали заметку про...' или 'удали все заметки'."
    )
    await message.answer(greeting)

async def process_text_via_api(message: types.Message, text: str):
    # Показываем статус "Печатает..." пока ждём ответа от FastAPI / ИИ
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    async with aiohttp.ClientSession() as session:
        try:
            payload = {"text": text, "tg_chat_id": message.chat.id}
            async with session.post(PROCESS_URL, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    intent = data.get("intent")
                    
                    if intent == "SEARCH":
                        results = data.get("results", [])
                        if results:
                            msg = "🔍 Найдено по вашему запросу:\n\n"
                            for r in results:
                                dt_str = ""
                                if r.get('created_at'):
                                    dt = datetime.fromisoformat(r['created_at'])
                                    dt_str = f" 🕒 {dt.astimezone(MSK).strftime('%d.%m.%Y %H:%M')}"
                                msg += f"- {r.get('structured_text') or r['text']}{dt_str}\n\n"
                            await message.answer(msg)
                        else:
                            await message.answer("🤷‍♂️ Ничего не найдено.")
                    elif intent == "LIST_ALL":
                        results = data.get("results", [])
                        if results:
                            msg = "📚 Все ваши заметки:\n\n"
                            for r in results:
                                dt_str = ""
                                if r.get('created_at'):
                                    dt = datetime.fromisoformat(r['created_at'])
                                    dt_str = f" 🕒 {dt.astimezone(MSK).strftime('%d.%m.%Y %H:%M')}"
                                msg += f"- {r.get('structured_text') or r['text']}{dt_str}\n\n"
                            await message.answer(msg)
                        else:
                            await message.answer("🤷‍♂️ У вас пока нет заметок.")
                    elif intent == "LIST_TAGS":
                        await message.answer("🏷 Доступные теги: РАБОТА, ОТДЫХ, УЧЕБА, ХОББИ, БЫТОВУХА, НАПОМИНАНИЕ, СПИСКИ, РАЗНОЕ")
                    elif intent == "LIST_REMINDERS":
                        results = data.get("results", [])
                        if results:
                            msg = "⏰ Ваши активные напоминания:\n\n"
                            for r in results:
                                dt = datetime.fromisoformat(r['remind_at'])
                                dt_str = dt.astimezone(MSK).strftime('%d.%m.%Y %H:%M:%S МСК')
                                rec_str = f"\n🔄 Повтор: {r['recurrence']}" if r.get('recurrence') else ""
                                rep_str = f" (осталось раз: {r['repetitions']})" if r.get('repetitions') else ""
                                msg += f"📌 {r['text']}\nСработает: {dt_str}{rec_str}{rep_str}\n\n"
                            await message.answer(msg)
                        else:
                            await message.answer("🤷‍♂️ У вас нет активных напоминаний.")
                    elif intent == "REMINDER":
                        rec = f"\n🔄 Цикл: {data.get('recurrence')}" if data.get('recurrence') else ""
                        rep = f" ({data.get('repetitions')} раз)" if data.get('repetitions') else ""
                        if data.get('remind_at'):
                            dt = datetime.fromisoformat(data['remind_at'])
                            dt_str = dt.astimezone(MSK).strftime('%d.%m %H:%M:%S МСК')
                        else: dt_str = ""
                        await message.answer(f"⏰ Напоминание установлено на {dt_str}!{rec}{rep}\nТекст: {data.get('note', {}).get('text')}")
                    elif intent == "DELETE":
                        if data.get("success"):
                            texts = data.get("deleted_texts", [])
                            # Для обратной совместимости, если вдруг вернется старый формат
                            if not texts and data.get("deleted_text"):
                                texts = [data.get("deleted_text")]
                            texts_str = "\n\n".join([f"- {t}" for t in texts])
                            header = "Заметка удалена" if len(texts) == 1 else f"Удалено записей: {len(texts)}"
                            await message.answer(f"🗑 {header}. Оригиналы:\n\n{texts_str}")
                        else:
                            await message.answer("🤷‍♂️ Не нашел подходящую заметку для удаления.")
                    elif intent == "DELETE_ALL":
                        await message.answer("🧨 Все ваши заметки были успешно удалены!")
                    else:
                        await message.answer("✅ Заметка сохранена!")
                else:
                    await message.answer(f"❌ Ошибка сервера: {resp.status}")
        except Exception as e:
            await message.answer(f"❌ Ошибка соединения с API: {e}")

@dp.message(lambda msg: msg.voice is not None)
async def handle_voice(message: types.Message):
    temp_filename = f"{uuid.uuid4()}.ogg"
    try:
        # Показываем статус "Записывает голосовое..."
        await bot.send_chat_action(chat_id=message.chat.id, action="record_voice")
        file_id = message.voice.file_id
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, temp_filename)
        
        with open(temp_filename, "rb") as audio_file:
            transcription = await aclient.audio.transcriptions.create(
                model="whisper-large-v3", # Модель Groq для аудио
                file=audio_file
            )
        recognized_text = transcription.text
        await message.answer(f"🎤 Распознано: {recognized_text}\n\nОбрабатываю...")
        await process_text_via_api(message, recognized_text)
    except Exception as e:
        await message.answer(f"❌ Ошибка аудио: {e}")
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@dp.message(lambda msg: msg.text is not None and not msg.text.startswith("/"))
async def handle_text_message(message: types.Message):
    await process_text_via_api(message, message.text)

async def main():
    print("Бот запущен...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    if BOT_TOKEN:
        asyncio.run(main())
    else:
        print("ОШИБКА: Не задан BOT_TOKEN в .env")