from fastapi import FastAPI
from .routers.api_router import api_router

app = FastAPI(title='ZametkiTG', description='API для умной работы с заметками')

app.include_router(api_router, prefix='/api/v1')
