import os
import urllib.request
import urllib.parse
import logging
import re
from openai import OpenAI
from datetime import datetime, UTC, timedelta
from .celery_app import celery_app
from dotenv import load_dotenv

from .models import Zametka
from .database import sync_session_maker

load_dotenv()

logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv('AI_API_KEY'), base_url=os.getenv('AI_BASE_URL'))
# Отдельный клиент для векторов (OpenAI)
emb_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'), base_url=os.getenv('OPENAI_BASE_URL'))

TAGS = ['РАБОТА', 'ОТДЫХ', 'УЧЕБА', 'ХОББИ', 'БЫТОВУХА', 'НАПОМИНАНИЕ', 'СПИСКИ', 'РАЗНОЕ']


@celery_app.task
def generate_ai_tag_and_embedding(zametka_id: int, text: str):
    generated_tag = 'НЕ ОПРЕДЕЛЕНО'
    generated_embedding = None

    # 1. СТРУКТУРИРОВАНИЕ И ДВОЙНАЯ ПРОВЕРКА (СИСТЕМА КОНТРОЛЯ)
    structured_text = text
    try:
        struct_resp = client.chat.completions.create(
            model=os.getenv('AI_MODEL'),
            messages=[
                {"role": "system", "content": "Ты редактор. Исправь только явные опечатки. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО додумывать факты, генерировать рассказы, стихи или добавлять информацию. Оставь исходный смысл и объем. Если тебе прислали одно слово — верни одно слово."}, 
                {"role": "user", "content": text}
            ],
            temperature=0.0
        )
        candidate_text = struct_resp.choices[0].message.content.strip()
        
        verify_resp = client.chat.completions.create(
            model=os.getenv('AI_MODEL'),
            messages=[{"role": "system", "content": "Оцени, изменился ли смысл оригинального текста в новой версии. Ответь строго 'ДА' (смысл сохранен) или 'НЕТ' (смысл искажен)."}, {"role": "user", "content": f"Оригинал: {text}\nНовая версия: {candidate_text}"}],
            temperature=0.0
        )
        if "ДА" in verify_resp.choices[0].message.content.strip().upper():
            structured_text = candidate_text
    except Exception as e:
        logger.error(f"Ошибка AI структурирования: {e}")

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=os.getenv('AI_MODEL'),
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            f'Текст: "{structured_text}"\n\n'
                            f'Задание: Выбери для этого текста ОДНУ категорию из списка: '
                            f'[{", ".join(TAGS)}].\n'
                            'Напиши ТОЛЬКО слово из списка. Ничего больше.'
                        ),
                    }
                ],
                temperature=0.1,
                max_tokens=15,
            )
            tag = (
                response.choices[0].message.content.strip('.,!?; ').upper()
            )  # приводим в соответствие тегам
            if tag in TAGS:
                generated_tag = tag
                break
        except Exception as e:
            logger.error(f'Ошибка генерации тега, попытка {attempt + 1}: {e}')
            continue  # антивылет

    # Генерируем вектор текста
    try:
        emb_response = emb_client.embeddings.create(
            input=structured_text,
            model=os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3')
        )
        generated_embedding = emb_response.data[0].embedding
    except Exception as e:
        logger.error(f'Ошибка генерации эмбеддинга: {e}')

    # 2. ПОИСК КОНФЛИКТОВ И ОБЪЕДИНЕНИЙ ПО СМЫСЛУ
    conflict_found = False
    conflict_id = None
    with sync_session_maker() as session:
        if generated_embedding:
            from sqlalchemy import select
            query = select(Zametka).where(Zametka.id != zametka_id).order_by(Zametka.embedding.l2_distance(generated_embedding)).limit(1)
            closest = session.execute(query).scalars().first()
            if closest:
                try:
                    conflict_resp = client.chat.completions.create(
                        model=os.getenv('AI_MODEL'),
                        messages=[{"role": "system", "content": "Сравни две заметки. Говорят ли они об одном и том же, но с ПРЯМЫМ противоречием в фактах? Ответь строго 'ДА' (есть конфликт) или 'НЕТ'."},
                                  {"role": "user", "content": f"Заметка 1: {structured_text}\nЗаметка 2: {closest.structured_text or closest.text}"}],
                        temperature=0.0
                    )
                    if "ДА" in conflict_resp.choices[0].message.content.strip().upper():
                        conflict_found = True
                        conflict_id = closest.id
                except:
                    pass

        zametka = session.get(Zametka, zametka_id)
        if zametka:
            zametka.tag = generated_tag
            zametka.structured_text = structured_text
            zametka.has_conflict = conflict_found
            zametka.conflict_with_id = conflict_id
            if generated_embedding:
                zametka.embedding = generated_embedding
            session.commit()
            
            if conflict_found and zametka.tg_chat_id:
                bot_token = os.getenv("BOT_TOKEN")
                if bot_token:
                    msg = urllib.parse.quote(f"⚠️ Конфликт версий!\nВаша заметка противоречит заметке #{conflict_id}. Зайдите в Web-интерфейс для проверки.")
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={zametka.tg_chat_id}&text={msg}"
                    req = urllib.request.Request(url)
                    try: urllib.request.urlopen(req, timeout=10)
                    except: pass


@celery_app.task
def daily_summary():
    """
    Планировщик собирает сводку за день.
    """
    from datetime import datetime, timedelta
    from sqlalchemy import select
    
    yesterday = datetime.utcnow() - timedelta(days=1)
    with sync_session_maker() as session:
        # Находим всех уникальных пользователей, которые создавали заметки за 24ч
        users_query = select(Zametka.tg_chat_id).where(
            Zametka.created_at >= yesterday, 
            Zametka.tg_chat_id.isnot(None)
        ).distinct()
        active_users = session.execute(users_query).scalars().all()
        
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            logger.warning("BOT_TOKEN не задан, сводка отменена.")
            return

        for chat_id in active_users:
            notes_query = select(Zametka).where(
                Zametka.created_at >= yesterday,
                Zametka.tg_chat_id == chat_id
            ).order_by(Zametka.created_at.desc()).limit(10)
            notes = session.execute(notes_query).scalars().all()
            
            if notes:
                summary = "🌅 Утренняя сводка мыслей за день:\n\n"
                for n in notes:
                    summary += f"- {n.title} (Тег: {n.tag})\n"
                
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={urllib.parse.quote(summary)}"
                req = urllib.request.Request(url)
                try: urllib.request.urlopen(req, timeout=10)
                except Exception as e: logger.error(f"Failed to send summary to {chat_id}: {e}")


@celery_app.task
def check_reminders():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token: return

    now = datetime.now(UTC)
    from sqlalchemy import select
    with sync_session_maker() as session:
        query = select(Zametka).where(
            Zametka.remind_at <= now,
            Zametka.is_reminded == False,
            Zametka.tg_chat_id.isnot(None)
        )
        reminders = session.execute(query).scalars().all()

        for reminder in reminders:
            text = urllib.parse.quote(f"⏰ Напоминание:\n{reminder.text}")
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={reminder.tg_chat_id}&text={text}"
            req = urllib.request.Request(url)
            try:
                urllib.request.urlopen(req, timeout=10)
                if reminder.recurrence:
                    if reminder.repetitions is not None:
                        reminder.repetitions -= 1
                        if reminder.repetitions <= 0:
                            reminder.is_reminded = True
                    if not reminder.is_reminded:
                        match = re.match(r'^(\d+)([smhdw])$', reminder.recurrence)
                        if match:
                            v, u = int(match.group(1)), match.group(2)
                            d = timedelta(seconds=v) if u=='s' else timedelta(minutes=v) if u=='m' else timedelta(hours=v) if u=='h' else timedelta(days=v) if u=='d' else timedelta(weeks=v)
                            reminder.remind_at += d
                        elif ',' in reminder.recurrence or reminder.recurrence.isdigit():
                            days = [int(x) for x in reminder.recurrence.split(',') if x.isdigit()]
                            if days:
                                nxt = reminder.remind_at + timedelta(days=1)
                                while nxt.weekday() not in days: nxt += timedelta(days=1)
                                reminder.remind_at = nxt
                            else: reminder.is_reminded = True
                        else: reminder.is_reminded = True
                else:
                    reminder.is_reminded = True

                if reminder.is_reminded:
                    session.delete(reminder)
            except Exception as e:
                logger.error(f"Failed to send reminder {reminder.id}: {e}")
        if reminders: session.commit()