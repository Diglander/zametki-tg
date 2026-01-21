from pydantic import BaseModel, Field, ConfigDict, model_validator
from datetime import datetime, UTC
from typing import Self


class ZametkaIn(BaseModel):
    title: str | None = Field(None, max_length = 100, description = 'Название заметки (необязательно)')
    text: str = Field(min_length = 1, description = 'Текст заметки')
    
    @model_validator(mode = 'after')
    def fill_title(self) -> Self:
        '''
        здесь мы заполняем title если он не был передан
        мы берем >=5 первых слов и делаем из них title
        '''
        if self.title is None:
            preview = self.text[:500] # против переполнения
            title = preview.split()
            if len(title) < 5:
                self.title = (' '.join(title))[:100]
                return self
            for i in range(5):
                if (title[i][-1] in ['.' , ',' , ':' , ';' , '!' , '?']):
                    self.title = (' '.join(title[:(i+1)]))[:100]
                    return self
            else:
                self.title = (' '.join(title[:5]) + '...')[:100] 
                return self
        return self


class ZametkaOut(BaseModel):
    id: int = Field(description = 'ID заметки из БД')
    title: str | None = Field(description = 'Название заметки')
    text: str = Field(description = 'Текст заметки')
    
    created_at: datetime = Field(description = 'Время создания из БД')
    updated_at: datetime | None = Field(None, description='Время обновления')

    model_config = ConfigDict(from_attributes=True)