from pydantic import BaseModel, Field, model_validator
from datetime import datetime, UTC
from typing import Self


class ZametkaIn(BaseModel):
    title: str | None = Field(None, max_length = 100, description = 'Название заметки (необязательно)')
    text: str = Field(min_length = 1, description = 'Текст заметки')
    data: datetime = Field(default_factory = lambda: datetime.now(UTC), description = 'Время создания (автоматически)')
    
    @model_validator(mode = 'after')
    def fill_title(self) -> Self:
        if self.title is None:
            title = self.text.split()
            if len(title) < 5:
                self.title = ' '.join(title)
                return self
            elif (title[4][-1] in ['.' , ',' , ':' , ';' , '!' , '?']):
                self.title = ' '.join(title[:5])
                return self
            else:
                self.title = ' '.join(title[:5]) + '...' 
                return self
        return self


class ZametkaOut(BaseModel):
    id: int = Field(default_factory = lambda: int(datetime.now(UTC).timestamp()), description = 'ID заметки')
    title: str | None = Field(description = 'Название заметки')
    text: str = Field(description = 'Текст заметки')
    data: datetime = Field(description = 'Время создания (автоматически)')