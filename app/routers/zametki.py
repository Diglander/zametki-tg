from fastapi import APIRouter, HTTPException
from ..schemas import ZametkaOut, ZametkaIn

router = APIRouter()

fake_db: dict[int, ZametkaOut] = {}

@router.post('/', response_model = ZametkaOut, status_code = 201, description = 'Создание новой заметки')
def create_zametka(zametka: ZametkaIn) -> ZametkaOut:
    zametka_out = ZametkaOut(**zametka.model_dump())
    fake_db[zametka_out.id] = zametka_out
    return zametka_out

@router.get('/{id}', response_model = ZametkaOut, description = 'Получение заметки по ID')
def get_zametka(id: int) -> ZametkaOut:
    if id in fake_db:
        return fake_db[id]
    else:
        raise HTTPException(status_code = 404, detail = 'Заметка не найдена')

@router.delete('/{id}', response_model = ZametkaOut, description = 'Удаление заметки по ID')
def delete_zametka(id: int) -> ZametkaOut:
    if id in fake_db:
        return fake_db.pop(id)
    else:
        raise HTTPException(status_code = 404, detail = 'Заметка не найдена')

@router.get('/', response_model = list[ZametkaOut], description = 'Получение всех заметок')
def get_all() -> list[ZametkaOut]:
    return list(fake_db.values())