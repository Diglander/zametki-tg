import os
import json
import re
import logging
from datetime import datetime, UTC
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from openai import AsyncOpenAI

from ..schemas import ZametkaOut, ZametkaIn, ZametkaUpdate, ProcessRequest
from ..database import get_session
from ..models import Zametka
from ..tasks import generate_ai_tag_and_embedding

router = APIRouter()

aclient = AsyncOpenAI(api_key=os.getenv('AI_API_KEY'), base_url=os.getenv('AI_BASE_URL'))

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
    now_iso = datetime.now(UTC).isoformat()
    prompt = f"""Ты — умный AI-ассистент. Текущее время (UTC): {now_iso}.
Определи намерение пользователя из текста.
Категории:
- SEARCH: поиск по заметкам (команды типа "найди", "покажи", "есть ли")
- REMINDER: создать напоминание с привязкой ко времени ("напомни", "через N дней/часов")
- NOTE: обычная заметка (сохранить факт, мысль, список)

Ответь строго в JSON без маркдауна (только объект {{...}}):
{{
    "intent": "SEARCH" | "REMINDER" | "NOTE",
    "query": "смысловой текст для поиска (только если SEARCH)",
    "remind_at": "ISO 8601 время UTC (только если REMINDER)",
    "text": "очищенный текст для сохранения (для NOTE или REMINDER, без слова 'напомни')"
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

    if intent == "SEARCH":
        q = parsed.get("query", req.text)
        emb_resp = await aclient.embeddings.create(input=q, model="text-embedding-3-small")
        q_emb = emb_resp.data[0].embedding
        query = select(Zametka).order_by(Zametka.embedding.l2_distance(q_emb)).limit(5)
        res = await session.execute(query)
        return {"intent": "SEARCH", "results": [{"text": n.text, "structured_text": n.structured_text, "id": n.id} for n in res.scalars().all()]}

    remind_at = None
    if intent == "REMINDER" and parsed.get("remind_at"):
        try:
            remind_str = parsed["remind_at"].replace("Z", "+00:00")
            # Фикс багов ISO форматов с/без микросекунд
            if len(remind_str) > 0:
                remind_at = datetime.fromisoformat(remind_str)
                # Убедимся, что время в UTC
                if remind_at.tzinfo is None:
                    remind_at = remind_at.replace(tzinfo=UTC)
        except Exception as e: 
            logger.warning(f"Failed to parse remind_at date: {parsed['remind_at']}. Error: {e}")

    note_text = parsed.get("text", req.text)
    new_zametka = Zametka(title=note_text[:50] + "...", text=note_text, tg_chat_id=req.tg_chat_id, remind_at=remind_at)
    session.add(new_zametka)
    await session.commit()
    await session.refresh(new_zametka)
    generate_ai_tag_and_embedding.delay(new_zametka.id, new_zametka.text)

    return {
        "intent": intent,
        "remind_at": remind_at.isoformat() if remind_at else None,
        "note": {"id": new_zametka.id, "text": new_zametka.text}
    }

@router.get('/search', response_model=list[ZametkaOut], description='Умный семантический поиск')
async def search_zametki(q: str, session: AsyncSession = Depends(get_session)) -> list[ZametkaOut]:
    # 1. Делаем вектор из запроса
    response = await aclient.embeddings.create(
        input=q,
        model="text-embedding-3-small"
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
