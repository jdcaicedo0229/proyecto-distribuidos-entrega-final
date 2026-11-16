import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
import httpx
from app import group
from app.storage import Store

class Client:
    def __init__(self,code):self.code=code;self.calls=0
    async def post(self,*args,**kwargs):
        self.calls+=1
        if self.code=='timeout':raise httpx.ReadTimeout('simulado')
        return httpx.Response(self.code,request=httpx.Request('POST','http://test/messages'))

class SenderTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self,code):
        with tempfile.TemporaryDirectory() as d:
            store=Store(str(Path(d)/'db'),'ga');store.add_user('ana')
            message,_=store.create('ana','hola',str(uuid4()))
            group.app.state.store=store;group.app.state.http=Client(code)
            group.state['central']='online'
            async def stop(_):raise asyncio.CancelledError
            with patch.object(group.asyncio,'sleep',stop):
                with self.assertRaises(asyncio.CancelledError):await group.sender()
            row=dict(store.db.execute('SELECT * FROM outbox').fetchone())
            self.assertEqual(row['id'],str(message.id));self.assertEqual(row['attempts'],1)
            store.close()
            return row
    async def test_503_is_retried(self):
        self.assertEqual((await self.run_case(503))['state'],'pending')
    async def test_400_is_terminal(self):
        self.assertEqual((await self.run_case(400))['state'],'rejected')
    async def test_429_is_terminal_per_assignment(self):
        self.assertEqual((await self.run_case(429))['state'],'rejected')
    async def test_timeout_is_retried(self):
        self.assertEqual((await self.run_case('timeout'))['state'],'pending')
    async def test_success_is_marked_sent(self):
        self.assertEqual((await self.run_case(200))['state'],'sent')
