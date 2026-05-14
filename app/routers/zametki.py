import os
import json
import re
import logging
from datetime import datetime, UTC, timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from openai import AsyncOpenAI

from ..schemas import ZametkaOut, ZametkaIn, ZametkaUpdate, ProcessRequest
from ..database import get_session
from ..models import Zametka
from ..tasks import generate_ai_tag_and_embedding

router = APIRouter()

aclient = AsyncOpenAI(api_key=os.getenv('AI_API_KEY'), base_url=os.getenv('AI_BASE_URL'))
# Отдельный клиент для эмбеддингов (OpenAI)
emb_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'), base_url=os.getenv('OPENAI_BASE_URL'))

logger = logging.getLogger(__name__)


@router.post(
    '/',
    response_model=ZametkaOut,
    status_code=status.HTTP_201_CREATED,
    description='Создание новой заметки',
)
async def create_zametka(
    zametka: ZametkaIn, session: AsyncSession = Depends(get_session)
) -> ZametkaOut:
    new_zametka = Zametka(**zametka.model_dump())
    session.add(new_zametka)
    await session.commit()
    await session.refresh(new_zametka)  # получаем id и время создания из БД
    generate_ai_tag_and_embedding.delay(new_zametka.id, new_zametka.text)  # генерируем хэштег и вектор
    return new_zametka


@router.post('/process', description='Интеллектуальный роутинг (Заметка/Поиск/Напоминание)')
async def process_text(
    req: ProcessRequest, session: AsyncSession = Depends(get_session)
):
    now_msk = datetime.now(UTC) + timedelta(hours=3)
    prompt = f"""Ты — умный AI-ассистент. Текущее время: {now_msk.strftime('%Y-%m-%d %H:%M:%S')}.
Категории СТРОГО разделены:
- SEARCH: ТОЛЬКО поиск конкретных заметок ("покажи про спорт", "найди рецепт").
- LIST_ALL: ТОЛЬКО показ ВСЕХ заметок ("покажи все заметки", "выведи все").
- DELETE: ТОЛЬКО удаление конкретной заметки или напоминания ("удали заметку про...", "отмени таймер").
- DELETE_ALL: ТОЛЬКО удаление ВСЕХ заметок ("удали все заметки", "очисти базу").
- LIST_REMINDERS: показать таймеры ("какие есть таймеры").
- LIST_TAGS: показать теги.
- REMINDER: создать напоминание ("напомни...").
- NOTE: просто сохранить текст, если не просят показать или удалить.

Ответь строго в JSON без маркдауна (только объект {{...}}):
{{
    "intent": "SEARCH" | "LIST_ALL" | "REMINDER" | "LIST_REMINDERS" | "LIST_TAGS" | "DELETE" | "DELETE_ALL" | "NOTE",
    "query": "СУТЬ того, что нужно найти или удалить (например, 'купить хлеб' вместо 'удали таймер про хлеб')",
    "is_reminder": "укажи true (boolean) если просят удалить/найти именно напоминание или таймер, иначе false",
    "delete_multiple": "укажи true (boolean) если просят удалить СРАЗУ НЕСКОЛЬКО или ВСЕ заметки по одной теме (например 'удали все про банан'), иначе false",
    "remind_at": "ISO 8601 время (только если REMINDER)",
    "recurrence": "интервал. ОБЯЗАТЕЛЬНО заполни, если просят цикл или 'через X N раз' (например, 'через 10 секунд' -> '10s'). Форматы: '10s', '5m', '3h', '1d', '1w' ИЛИ '0,2,4' (дни недели). Иначе null",
    "repetitions": "число повторений (например, 3), если указано, иначе null",
    "text": "исходный текст БЕЗ отсебятины. ЗАПРЕЩЕНО писать сочинения или додумывать факты. Сохрани оригинальный смысл и объем."
}}"""
    try:
        response = await aclient.chat.completions.create(
            model=os.getenv('AI_MODEL', 'llama-3.3-70b-versatile'),
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": req.text}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        raw = response.choices[0].message.content.strip()
        
        # Отказоустойчивый поиск JSON блока в ответе LLM
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
        else:
            parsed = json.loads(raw) # fallback
        intent = parsed.get("intent", "NOTE")
    except Exception as e:
        logger.error(f"LLM Intent Parse Error: {e} | Raw string: {raw if 'raw' in locals() else 'N/A'}")
        intent = "NOTE"
        parsed = {"text": req.text}

    if intent == "LIST_TAGS":
        return {"intent": "LIST_TAGS"}

    if intent == "SEARCH":
        q = parsed.get("query", req.text)
        emb_resp = await emb_client.embeddings.create(input=q, model=os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3'))
        q_emb = emb_resp.data[0].embedding
        query = select(Zametka).where(Zametka.tg_chat_id == req.tg_chat_id).order_by(Zametka.embedding.l2_distance(q_emb)).limit(5)
        res = await session.execute(query)
        return {"intent": "SEARCH", "results": [{"text": n.text, "structured_text": n.structured_text, "id": n.id} for n in res.scalars().all()]}

    if intent == "LIST_ALL":
        query = select(Zametka).where(Zametka.tg_chat_id == req.tg_chat_id).order_by(Zametka.created_at.desc()).limit(50)
        res = await session.execute(query)
        return {"intent": "LIST_ALL", "results": [{"text": n.text, "structured_text": n.structured_text, "id": n.id} for n in res.scalars().all()]}

    if intent == "LIST_REMINDERS":
        query = select(Zametka).where(
            Zametka.remind_at.isnot(None),
            Zametka.is_reminded == False,
            Zametka.tg_chat_id == req.tg_chat_id
        ).order_by(Zametka.remind_at.asc()).limit(10)
        res = await session.execute(query)
        reminders = res.scalars().all()
        return {
            "intent": "LIST_REMINDERS",
            "results": [{"text": n.structured_text or n.text, "remind_at": n.remind_at.isoformat(), "recurrence": n.recurrence, "repetitions": n.repetitions} for n in reminders]
        }

    if intent == "DELETE":
        q = parsed.get("query", req.text)
        is_reminder = parsed.get("is_reminder")
        if isinstance(is_reminder, str):
            is_reminder = is_reminder.lower() == 'true'
        delete_multiple = parsed.get("delete_multiple")
        if isinstance(delete_multiple, str):
            delete_multiple = delete_multiple.lower() == 'true'

        stmt = select(Zametka).where(Zametka.tg_chat_id == req.tg_chat_id)
        if is_reminder:
            stmt = stmt.where(Zametka.remind_at.isnot(None))

        limit_count = 10 if delete_multiple else 1

        # 1. Пытаемся сначала найти точное вхождение текста (идеально для коротких таймеров)
        exact_query = stmt.where(Zametka.text.ilike(f"%{q}%")).order_by(Zametka.created_at.desc()).limit(limit_count)
        res = await session.execute(exact_query)
        notes_to_delete = res.scalars().all()

        # 2. Если по точному тексту не нашли, ищем по смыслу (вектору)
        if not notes_to_delete:
            emb_resp = await emb_client.embeddings.create(input=q, model=os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3'))
            q_emb = emb_resp.data[0].embedding
            vec_limit = 5 if delete_multiple else 1
            vec_query = stmt.where(Zametka.embedding.isnot(None)).order_by(Zametka.embedding.l2_distance(q_emb)).limit(vec_limit)
            res = await session.execute(vec_query)
            notes_to_delete = res.scalars().all()

        if notes_to_delete:
            deleted_texts = [n.text for n in notes_to_delete]
            for n in notes_to_delete:
                await session.delete(n)
            await session.commit()
            return {"intent": "DELETE", "success": True, "deleted_texts": deleted_texts}
        return {"intent": "DELETE", "success": False}

    if intent == "DELETE_ALL":
        query = delete(Zametka).where(Zametka.tg_chat_id == req.tg_chat_id)
        await session.execute(query)
        await session.commit()
        return {"intent": "DELETE_ALL", "success": True}

    remind_at = None
    if intent == "REMINDER":
        if parsed.get("remind_at"):
            try:
                # ИИ выдает время по Москве. Очищаем строку от таймзон, чтобы получить просто дату/время.
                remind_str = parsed["remind_at"]
                if remind_str.endswith("Z"):
                    remind_str = remind_str[:-1]
                if "+" in remind_str:
                    remind_str = remind_str.split("+")[0]
                    
                if len(remind_str) > 0:
                    naive_dt = datetime.fromisoformat(remind_str)
                    # Программно отнимаем 3 часа и сохраняем в UTC для базы данных
                    remind_at = (naive_dt - timedelta(hours=3)).replace(tzinfo=UTC)
            except Exception as e: 
                logger.warning(f"Failed to parse remind_at date: {parsed['remind_at']}. Error: {e}")
        
        # Если ИИ не вернул remind_at, но вернул recurrence (например, "каждые 10 секунд")
        recurrence_str = parsed.get("recurrence")
        if not remind_at and recurrence_str:
            match = re.match(r'^(\d+)([smhdw])$', recurrence_str)
            if match:
                v, u = int(match.group(1)), match.group(2)
                d = timedelta(seconds=v) if u=='s' else timedelta(minutes=v) if u=='m' else timedelta(hours=v) if u=='h' else timedelta(days=v) if u=='d' else timedelta(weeks=v)
                remind_at = datetime.now(UTC) + d
            else:
                remind_at = datetime.now(UTC)

    note_text = parsed.get("text", req.text)
    recurrence = parsed.get("recurrence")
    repetitions = parsed.get("repetitions")
    new_zametka = Zametka(title=note_text[:50] + "...", text=note_text, tg_chat_id=req.tg_chat_id, remind_at=remind_at, recurrence=recurrence, repetitions=repetitions)
    session.add(new_zametka)
    await session.commit()
    await session.refresh(new_zametka)
    generate_ai_tag_and_embedding.delay(new_zametka.id, new_zametka.text)

    return {
        "intent": intent,
        "recurrence": recurrence,
        "repetitions": repetitions,
        "remind_at": remind_at.isoformat() if remind_at else None,
        "note": {"id": new_zametka.id, "text": new_zametka.text}
    }

@router.get('/search', response_model=list[ZametkaOut], description='Умный семантический поиск')
async def search_zametki(q: str, session: AsyncSession = Depends(get_session)) -> list[ZametkaOut]:
    # 1. Делаем вектор из запроса
    response = await emb_client.embeddings.create(
        input=q,
        model=os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3')
    )
    query_embedding = response.data[0].embedding

    # 2. Ищем через pgvector ближайшие заметки (<-> это l2_distance)
    query = select(Zametka).order_by(Zametka.embedding.l2_distance(query_embedding)).limit(5)
    result = await session.execute(query)
    return result.scalars().all()


@router.get('/{id}', response_model=ZametkaOut, description='Получение заметки по ID')
async def get_zametka(id: int, session: AsyncSession = Depends(get_session)) -> ZametkaOut:
    query = select(Zametka).where(Zametka.id == id)
    result = await session.execute(query)
    zametka = result.scalars().first()
    if not zametka:
        raise HTTPException(status_code=404, detail='Заметка не найдена')
    return zametka


@router.put('/{id}', response_model=ZametkaOut, description='Обновление заметки по ID')
async def update_zametka(
    id: int, update_zametka: ZametkaUpdate, session: AsyncSession = Depends(get_session)
) -> ZametkaOut:
    need_ai = False
    zametka = await session.get(Zametka, id)
    if not zametka:
        raise HTTPException(status_code=404, detail='Заметка не найдена')
    if update_zametka.title is not None:
        zametka.title = update_zametka.title
    if update_zametka.text is not None:
        zametka.text = update_zametka.text
        need_ai = True
    await session.commit()
    await session.refresh(zametka)
    if need_ai:
        generate_ai_tag_and_embedding.delay(id, update_zametka.text)  # генерируем тег и вектор ПОСЛЕ коммита
    return zametka


@router.delete(
    '/{id}',
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    description='Удаление заметки по ID',
)
async def delete_zametka(id: int, session: AsyncSession = Depends(get_session)) -> None:
    query = select(Zametka).where(Zametka.id == id)
    result = await session.execute(query)
    zametka = result.scalars().first()
    if not zametka:
        raise HTTPException(status_code=404, detail='Заметка не найдена')
    await session.delete(zametka)
    await session.commit()
    return None


@router.get('/', response_model=list[ZametkaOut], description='Получение всех заметок')
async def get_all(session: AsyncSession = Depends(get_session)) -> list[ZametkaOut]:
    query = select(Zametka)
    result = await session.execute(query)
    zametki = result.scalars().all()
    return zametki
