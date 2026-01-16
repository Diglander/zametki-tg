from fastapi import APIRouter

router = APIRouter()

@router.get('/', response_model = str, description = 'Интро')
def intro() -> str:
    return "Hello Zametki's world! http://127.0.0.1:8000/docs"