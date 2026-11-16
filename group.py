"""Servidor de grupo. Ejecutar con un solo worker (reloj y SQLite locales)."""
import asyncio
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from app.common import Message, User, Send, event, delay, history_messages
from app.storage import Store

SERVER = os.getenv('GROUP_ID', 'ga')
CENTRAL = os.getenv('CENTRAL_URL', 'http://localhost:8000').rstrip('/')
PUBLIC = os.getenv('PUBLIC_URL', 'http://localhost:8001').rstrip('/')
HEARTBEAT = float(os.getenv('HEARTBEAT_INTERVAL', '2'))
FAILURES = int(os.getenv('FAILURE_THRESHOLD', '3'))
SYNC = float(os.getenv('SYNC_INTERVAL', '5'))
RENEW = float(os.getenv('REGISTER_INTERVAL', '10'))
state = {'central': 'unknown', 'failures': 0, 'registered': False,
         'last_sync': None, 'sync_error': None, 'registration_error': None}

async def heartbeat():
    while True:
        try:
            r = await app.state.http.get(CENTRAL + '/health')
            r.raise_for_status()
            if state['central'] != 'online':
                event('central_online', server=SERVER)
                app.state.wake.set()
            state.update(central='online', failures=0)
        except (httpx.HTTPError, ValueError) as exc:
            state['failures'] += 1
            if state['failures'] >= FAILURES:
                if state['central'] != 'offline':
                    event('central_offline', server=SERVER, failures=state['failures'])
                state.update(central='offline', registered=False)
        await asyncio.sleep(HEARTBEAT)

async def register_and_sync():
    next_register = next_sync = 0
    register_attempt = sync_attempt = 0
    register_blocked = sync_blocked = False
    while True:
        if app.state.wake.is_set():
            app.state.wake.clear()
            next_register = next_sync = 0
        now = time.monotonic()
        if now >= next_register and not register_blocked:
            try:
                r = await app.state.http.post(CENTRAL + '/register', json={'server': SERVER, 'url': PUBLIC})
                if 400 <= r.status_code < 500:
                    register_blocked = True
                    state['registration_error'] = f'HTTP {r.status_code}; corregir configuración y reiniciar'
                    state['registered'] = False
                    event('register_rejected', status=r.status_code)
                else:
                    r.raise_for_status()
                    state.update(registered=True, registration_error=None)
                    register_attempt = 0
                    event('registered', server=SERVER, url=PUBLIC)
                next_register = time.monotonic() + RENEW
            except httpx.HTTPError as exc:
                register_attempt += 1
                state.update(registered=False, registration_error=str(exc))
                next_register = time.monotonic() + delay(register_attempt)
                event('register_retry', attempt=register_attempt, error=str(exc))
        if now >= next_sync and not sync_blocked:
            try:
                # Reconciliación completa: mensajes tardíos pueden tener Lamport menor.
                # No usar el reloj local como cursor. Adaptar paginación al OpenAPI real.
                r = await app.state.http.get(CENTRAL + '/history', params={'since': 0})
                if 400 <= r.status_code < 500:
                    sync_blocked = True
                    state['sync_error'] = f'HTTP {r.status_code}; revisar protocolo y reiniciar'
                    event('history_rejected', status=r.status_code)
                else:
                    r.raise_for_status()
                    messages = history_messages(r.json())
                    added = 0
                    for msg in messages:
                        fresh = app.state.store.receive(msg)
                        added += fresh
                        if fresh:
                            event('recovered', id=str(msg.id), lamport=msg.lamport, origin=msg.origin)
                    state.update(last_sync=time.time(), sync_error=None)
                    sync_attempt = 0
                    event('history_synced', added=added, inspected=len(messages))
                next_sync = time.monotonic() + SYNC
            except (httpx.HTTPError, ValueError) as exc:
                sync_attempt += 1
                state['sync_error'] = str(exc)
                next_sync = time.monotonic() + delay(sync_attempt)
                event('history_retry', error=str(exc), attempt=sync_attempt)
        await asyncio.sleep(.2)

async def sender():
    while True:
        if state['central'] != 'offline':
            for item in app.state.store.pending():
                msg = app.state.store.get(item['id'])
                attempts = item['attempts'] + 1
                error = None
                try:
                    r = await app.state.http.post(CENTRAL + '/messages', json=msg.wire())
                    if 200 <= r.status_code < 300:
                        app.state.store.outcome(item['id'], 'sent', attempts)
                        event('sent', id=item['id'], lamport=msg.lamport, attempt=attempts)
                        continue
                    error = f'HTTP {r.status_code}: {r.text[:160]}'
                    if r.status_code < 500:
                        app.state.store.outcome(item['id'], 'rejected', attempts, error=error)
                        event('rejected', id=item['id'], lamport=msg.lamport, error=error)
                        continue
                except httpx.HTTPError as exc:
                    error = str(exc)
                wait = delay(attempts)
                app.state.store.outcome(item['id'], 'pending', attempts, time.time()+wait, error)
                event('retry', id=item['id'], lamport=msg.lamport, attempt=attempts, wait_s=wait, error=error)
        await asyncio.sleep(.15)

@asynccontextmanager
async def lifespan(app):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,32}', SERVER):
        raise ValueError('GROUP_ID inválido')
    if min(HEARTBEAT, FAILURES, SYNC, RENEW) <= 0:
        raise ValueError('Los intervalos y umbrales deben ser positivos')
    app.state.store = Store(os.getenv('DB_PATH', 'data/group.db'), SERVER)
    app.state.http = httpx.AsyncClient(timeout=float(os.getenv('HTTP_TIMEOUT', '3')), trust_env=False)
    app.state.wake = asyncio.Event()
    tasks = [asyncio.create_task(fn()) for fn in (heartbeat, register_and_sync, sender)]
    event('started', server=SERVER, central=CENTRAL)
    try:
        yield
    finally:
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await app.state.http.aclose()
        app.state.store.close()

app = FastAPI(title='Chat distribuido - servidor de grupo', lifespan=lifespan)

@app.get('/')
async def index():
    return FileResponse(Path(__file__).resolve().parent.parent / 'static/index.html')

@app.get('/fed/health')
async def health():
    return {'server': SERVER, 'lamport': app.state.store.clock()}

@app.post('/fed/messages')
async def receive(message: Message):
    fresh = app.state.store.receive(message)
    event('received' if fresh else 'duplicate_discarded', id=str(message.id), lamport=message.lamport,
          origin=message.origin)
    return {'status': 'ok'}

@app.get('/api/status')
async def status():
    return {**state, 'server': SERVER, 'lamport': app.state.store.clock(),
            'outbox': app.state.store.counts(), 'protocol': 'provisional-pdf-v2'}

@app.get('/api/users')
async def users():
    return app.state.store.users()

@app.post('/api/users')
async def create_user(user: User):
    app.state.store.add_user(user.username)
    return {'username': user.username, 'address': f'{user.username}@{SERVER}'}

@app.get('/api/messages')
async def messages():
    return app.state.store.history(with_status=True)

@app.post('/api/messages', status_code=202)
async def send(data: Send):
    try:
        message, fresh = app.state.store.create(data.username, data.body, str(data.request_id))
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    event('queued' if fresh else 'client_duplicate', id=str(message.id), lamport=message.lamport)
    return message.wire()
