import os
from openai import OpenAI
from .celery_app import celery_app
from dotenv import load_dotenv

from .models import Zametka
from .database import sync_session_maker

load_dotenv()

client = OpenAI(api_key=os.getenv('AI_API_KEY'), base_url=os.getenv('AI_BASE_URL'))

TAGS = ['РАБОТА', 'ОТДЫХ', 'УЧЕБА', 'ХОББИ', 'БЫТОВУХА', 'НАПОМИНАНИЕ', 'СПИСКИ', 'РАЗНОЕ']


@celery_app.task
def generate_ai_tag(zametka_id: int, text: str):
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=os.getenv('AI_MODEL'),
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            f'Текст: "{text}"\n\n'
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
                with sync_session_maker() as session:
                    zametka = session.get(Zametka, zametka_id)
                    zametka.tag = tag
                    session.commit()
                    return None
        except Exception as e:
            print(f'Ошибка {e} при работе с AI')
            continue  # антивылет
    with sync_session_maker() as session:
        zametka = session.get(Zametka, zametka_id)
        zametka.tag = 'НЕ ОПРЕДЕЛЕНО'
        session.commit()
        return None
        