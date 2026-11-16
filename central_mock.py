"""Simulador LOCAL del central. No es el servidor oficial del profesor."""
import asyncio
import os
import time
from contextlib import asynccontextmanager
from urllib.parse import urlparse
import httpx
from fastapi import FastAPI, HTTPException
from app.common import Register, Message, event, delay
from app.storage import Store

async def forward():
    while True:
        rows = app.state.store.db.execute('''SELECT d.*,p.url FROM deliveries d
            JOIN peers p ON p.server=d.server
            WHERE d.state='pending' AND d.next_at<=? AND p.expires>?
            ORDER BY d.rowid LIMIT 100''', (time.time(), time.time())).fetchall()
        for row in rows:
            msg = app.state.store.get(row['id'])
            attempts = row['attempts'] + 1
            outcome, error, next_at = 'pending', None, 0
            try:
                r = await app.state.http.post(row['url'] + '/fed/messages', json=msg.wire())
                if 200 <= r.status_code < 300:
                    outcome = 'sent'
                elif r.status_code < 500:
                    outcome, error = 'rejected', f'HTTP {r.status_code}'
                else:
                    error = f'HTTP {r.status_code}'
            except httpx.HTTPError as exc:
                error = str(exc)
            if outcome == 'pending': next_at = time.time() + delay(attempts)
            with app.state.store.db:
                app.state.store.db.execute('''UPDATE deliveries SET state=?,attempts=?,next_at=?,error=?
                    WHERE id=? AND server=?''', (outcome, attempts, next_at, error, row['id'], row['server']))
            event('central_delivery', id=row['id'], server=row['server'], state=outcome, error=error)
        await asyncio.sleep(.1)

@asynccontextmanager
async def lifespan(app):
    app.state.store = Store(os.getenv('DB_PATH', 'data/central.db'), 'central-mock')
    app.state.http = httpx.AsyncClient(timeout=1, trust_env=False)
    task = asyncio.create_task(forward())
    try: yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await app.state.http.aclose()
        app.state.store.close()

app = FastAPI(title='Central SIMULADO, solo laboratorio', lifespan=lifespan)

@app.get('/health')
async def health():
    return {'status': 'ok', 'simulated': True}

@app.post('/register')
async def register(data: Register):
    url = urlparse(data.url)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
        raise HTTPException(400, 'URL HTTP(S) inválida')
    with app.state.store.db:
        app.state.store.db.execute('''INSERT INTO peers VALUES(?,?,?)
            ON CONFLICT(server) DO UPDATE SET url=excluded.url,expires=excluded.expires''',
            (data.server, data.url.rstrip('/'), time.time()+30))
    return {'status': 'ok', 'lease_seconds': 30}

@app.post('/messages')
async def receive(message: Message):
    store = app.state.store
    # Una sola transacción conserva tanto mensaje como obligaciones de reenvío.
    with store.db:
        if store.get(str(message.id)):
            return {'status': 'ok'}
        store.insert(message)
        store.set_clock(max(store.clock(), message.lamport)+1)
        store.db.execute('''INSERT OR IGNORE INTO deliveries(id,server)
            SELECT ?,server FROM peers WHERE server<>? AND expires>?''',
            (str(message.id), message.origin, time.time()))
    event('central_received', id=str(message.id), lamport=message.lamport)
    return {'status': 'ok'}

@app.get('/history')
async def history(since: int = 0):
    return app.state.store.history(since)
