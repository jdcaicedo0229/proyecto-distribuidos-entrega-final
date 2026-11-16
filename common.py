"""Modelos y protocolo provisional: contrastar con el OpenAPI del profesor."""
import json
import logging
import os
import random
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger('chat')

def event(kind, **fields):
    log.info(json.dumps({'time': datetime.now().astimezone().isoformat(),
                         'event': kind, **fields}, ensure_ascii=False))

def delay(attempt):
    base = float(os.getenv('RETRY_BASE', '1'))
    cap = float(os.getenv('RETRY_MAX', '30'))
    return min(cap, base * 2 ** min(attempt - 1, 20)) * random.uniform(.8, 1.0)

class Message(BaseModel):
    model_config = ConfigDict(extra='ignore', populate_by_name=True)
    id: UUID
    sender: str = Field(alias='from', min_length=1)
    origin: str = Field(min_length=1)
    lamport: int = Field(ge=0, strict=True)
    sent_at: datetime
    body: str = Field(min_length=1)

    def wire(self):
        return self.model_dump(mode='json', by_alias=True)

class User(BaseModel):
    username: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,32}$')

class Send(BaseModel):
    username: str
    body: str = Field(min_length=1, max_length=4000)
    request_id: UUID

    @field_validator('body')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('El mensaje no puede estar vacío')
        return value

class Register(BaseModel):
    model_config = ConfigDict(extra='ignore')
    server: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,32}$')
    url: str


def history_messages(payload):
    # Dos envolturas habituales; ninguna se declara oficial sin el OpenAPI.
    if isinstance(payload, list):
        raw = payload
    elif isinstance(payload, dict) and isinstance(payload.get('messages'), list):
        if payload.get('has_more') or payload.get('next') or payload.get('next_cursor'):
            raise ValueError('Historial paginado: adaptar al OpenAPI oficial antes de usar')
        raw = payload['messages']
    else:
        raise ValueError('Formato /history desconocido: revisar especificación oficial')
    return [Message.model_validate(item) for item in raw]
