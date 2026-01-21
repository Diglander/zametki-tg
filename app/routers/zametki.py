from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..schemas import ZametkaOut, ZametkaIn
from ..database import get_session
from ..models import Zametka

router = APIRouter()

@router.post('/', response_model=ZametkaOut, status_code=status.HTTP_201_CREATED, description = 'Создание новой заметки')
async def create_zametka(
        zametka: ZametkaIn,
        session: AsyncSession = Depends(get_session) 
    ) -> ZametkaOut:
    new_zametka = Zametka(**zametka.model_dump())
    session.add(new_zametka)
    await session.commit()
    await session.refresh(new_zametka) # получаем id и время создания из БД
    return new_zametka

@router.get('/{id}', response_model = ZametkaOut, description = 'Получение заметки по ID')
async def get_zametka(
    id: int,
    session: AsyncSession = Depends(get_session)
    ) -> ZametkaOut:
    query = select(Zametka).where(Zametka.id == id)
    result = await session.execute(query)
    zametka = result.scalars().first()
    if not zametka:
        raise HTTPException(status_code = 404, detail = 'Заметка не найдена')
    return zametka

@router.delete('/{id}', response_model = None, status_code = status.HTTP_204_NO_CONTENT, description = 'Удаление заметки по ID')
async def delete_zametka(
    id: int,
    session: AsyncSession = Depends(get_session)
    ) -> None:
    query = select(Zametka).where(Zametka.id == id)
    result = await session.execute(query)
    zametka = result.scalars().first()
    if not zametka:
        raise HTTPException(status_code = 404, detail = 'Заметка не найдена')
    await session.delete(zametka)
    await session.commit()
    return None

@router.get('/', response_model = list[ZametkaOut], description = 'Получение всех заметок')
async def get_all(session: AsyncSession = Depends(get_session)) -> list[ZametkaOut]:
    query = select(Zametka)
    result = await session.execute(query)
    zametki = result.scalars().all()
    return zametki