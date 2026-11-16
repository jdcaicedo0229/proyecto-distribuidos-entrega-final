"""SQLite: historial, reloj y cola se confirman en la misma transacción."""
import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from app.common import Message

class Store:
    def __init__(self, path, server):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT OR IGNORE INTO meta VALUES('clock','0');
        CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS messages(
            id TEXT PRIMARY KEY, lamport INTEGER NOT NULL, origin TEXT NOT NULL,
            payload TEXT NOT NULL, received_at REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS message_order ON messages(lamport, origin, id);
        CREATE TABLE IF NOT EXISTS outbox(
            id TEXT PRIMARY KEY REFERENCES messages(id), state TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0, next_at REAL NOT NULL DEFAULT 0,
            error TEXT);
        CREATE TABLE IF NOT EXISTS requests(
            request_id TEXT PRIMARY KEY, message_id TEXT NOT NULL,
            username TEXT NOT NULL, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS peers(server TEXT PRIMARY KEY, url TEXT NOT NULL, expires REAL);
        CREATE TABLE IF NOT EXISTS deliveries(
            id TEXT NOT NULL, server TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            next_at REAL NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'pending', error TEXT,
            PRIMARY KEY(id,server));
        ''')
        identity = self.db.execute("SELECT value FROM meta WHERE key='server'").fetchone()
        if identity and identity[0] != server:
            self.db.close()
            raise ValueError('Este volumen pertenece a otro grupo. Use un volumen nuevo; conserve el anterior.')
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO meta VALUES('server',?)", (server,))
        self.server = server

    def clock(self):
        return int(self.db.execute("SELECT value FROM meta WHERE key='clock'").fetchone()[0])

    def set_clock(self, value):
        self.db.execute("UPDATE meta SET value=? WHERE key='clock'", (str(value),))

    def add_user(self, name):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO users VALUES(?)', (name,))

    def users(self):
        return [r[0] for r in self.db.execute('SELECT username FROM users ORDER BY username')]

    def create(self, username, body, request_id):
        with self.db:
            previous = self.db.execute('SELECT * FROM requests WHERE request_id=?', (request_id,)).fetchone()
            if previous:
                if previous['username'] != username or previous['body'] != body:
                    raise ValueError('request_id reutilizado con otro contenido')
                return self.get(previous['message_id']), False
            if username not in self.users():
                raise LookupError('Crea primero el usuario')
            clock = self.clock() + 1
            msg = Message(id=uuid4(), sender=f'{username}@{self.server}', origin=self.server,
                          lamport=clock, sent_at=datetime.now(timezone.utc), body=body)
            self.set_clock(clock)
            self.insert(msg)
            self.db.execute("INSERT INTO outbox(id,state) VALUES(?,'pending')", (str(msg.id),))
            self.db.execute('INSERT INTO requests VALUES(?,?,?,?)',
                            (request_id, str(msg.id), username, body))
            return msg, True

    def insert(self, msg):
        self.db.execute('INSERT INTO messages VALUES(?,?,?,?,?)',
                        (str(msg.id), msg.lamport, msg.origin, json.dumps(msg.wire()), time.time()))

    def receive(self, msg):
        with self.db:
            if self.get(str(msg.id)):
                return False  # Un duplicado tampoco modifica el reloj.
            self.set_clock(max(self.clock(), msg.lamport) + 1)
            self.insert(msg)
            return True

    def get(self, identifier):
        row = self.db.execute('SELECT payload FROM messages WHERE id=?', (identifier,)).fetchone()
        return Message.model_validate_json(row[0]) if row else None

    def history(self, since=-1, with_status=False):
        rows = self.db.execute('''SELECT m.payload, o.state, o.error FROM messages m
            LEFT JOIN outbox o ON m.id=o.id WHERE m.lamport>?
            ORDER BY m.lamport,m.origin,m.id''', (since,)).fetchall()
        result = []
        for row in rows:
            data = json.loads(row['payload'])
            if with_status:
                data['delivery'] = row['state'] or 'received'
                data['error'] = row['error']
            result.append(data)
        return result

    def pending(self):
        return self.db.execute("SELECT * FROM outbox WHERE state='pending' AND next_at<=? ORDER BY rowid LIMIT 50",
                               (time.time(),)).fetchall()

    def outcome(self, identifier, state, attempts, next_at=0, error=None):
        with self.db:
            self.db.execute('UPDATE outbox SET state=?,attempts=?,next_at=?,error=? WHERE id=?',
                            (state, attempts, next_at, error, identifier))

    def counts(self):
        return {r[0]: r[1] for r in self.db.execute('SELECT state,count(*) FROM outbox GROUP BY state')}

    def close(self):
        self.db.close()
