import asyncio
import os
import uuid
import aiohttp
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

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("Привет! Отправь мне текст или запиши голосовое. Я могу создавать заметки, искать по смыслу и ставить напоминания (например: 'напомни через 5 дней...').")

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
                            for r in results: msg += f"- {r.get('structured_text') or r['text']}\n\n"
                            await message.answer(msg)
                        else:
                            await message.answer("🤷‍♂️ Ничего не найдено.")
                    elif intent == "REMINDER":
                        await message.answer(f"⏰ Напоминание установлено!\nТекст: {data.get('note', {}).get('text')}")
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