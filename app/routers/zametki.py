from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..schemas import ZametkaOut, ZametkaIn, ZametkaUpdate
from ..database import get_session
from ..models import Zametka
from ..tasks import generate_ai_tag

router = APIRouter()


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
    generate_ai_tag.delay(new_zametka.id, new_zametka.text)  # генерируем хэштег
    return new_zametka


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
        generate_ai_tag.delay(id, update_zametka.text)  # генерирум тег ПОСЛЕ коммита
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
