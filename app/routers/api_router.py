from fastapi import APIRouter
from .zametki import router as zametki_router
from .intro import router as intro_router

api_router = APIRouter()

api_router.include_router(zametki_router, prefix='/Zametki', tags=['Заметки'])

api_router.include_router(intro_router, prefix='', tags=['Интро'])
