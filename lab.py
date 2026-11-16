"""Utilidades para pruebas reales HTTP sin paquetes adicionales al proyecto."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]

def request(url, method='GET', data=None, timeout=5):
    raw = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=raw, method=method, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)

def wait_for(fn, timeout=35):
    deadline = time.monotonic()+timeout
    last = None
    while time.monotonic() < deadline:
        try:
            value = fn()
            if value: return value
        except (OSError, ValueError) as exc: last=exc
        time.sleep(.1)
    raise TimeoutError(f'No se cumplió la condición en {timeout}s. Último error: {last}')

def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        return s.getsockname()[1]

class Lab:
    def __init__(self, directory, backend='processes'):
        self.directory=Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)
        self.backend=backend
        self.processes={}
        self.handles=[]
        if backend=='docker':
            self.urls={'central':'http://localhost:8000','a':'http://localhost:8001','b':'http://localhost:8002'}
        else:
            ports=set()
            while len(ports)<3: ports.add(free_port())
            self.urls={key:f'http://127.0.0.1:{port}' for key,port in zip(['central','a','b'],sorted(ports))}

    def start(self, key):
        if self.backend=='docker':
            service={'central':'central','a':'grupo-a','b':'grupo-b'}[key]
            subprocess.run(['docker','compose','up','-d',service],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        else:
            env={**os.environ,'DB_PATH':str(self.directory/f'{key}.db'),
                 'CENTRAL_URL':self.urls['central'],'PUBLIC_URL':self.urls[key],
                 'GROUP_ID':'g'+key,'PYTHONUNBUFFERED':'1'}
            handle=open(self.directory/f'{key}.log','a',encoding='utf-8')
            self.handles.append(handle)
            module='app.central_mock:app' if key=='central' else 'app.group:app'
            port=self.urls[key].rsplit(':',1)[1]
            self.processes[key]=subprocess.Popen([sys.executable,'-m','uvicorn',module,'--host','127.0.0.1',
                '--port',port],cwd=ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT)
        endpoint='/health' if key=='central' else '/fed/health'
        wait_for(lambda:request(self.urls[key]+endpoint))

    def stop(self,key):
        if self.backend=='docker':
            service={'central':'central','a':'grupo-a','b':'grupo-b'}[key]
            subprocess.run(['docker','compose','kill',service],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        elif key in self.processes:
            p=self.processes.pop(key)
            p.kill()
            p.wait(timeout=10)

    def boot(self):
        for key in ['central','a','b']: self.start(key)
        for key in ['a','b']:
            wait_for(lambda:request(self.urls[key]+'/api/status')['registered'])
            request(self.urls[key]+'/api/users','POST',{'username':'prueba'})

    def send(self,key,body,request_id=None):
        return request(self.urls[key]+'/api/messages','POST',
            {'username':'prueba','body':body,'request_id':request_id or str(uuid4())})

    def messages(self,key):
        return request(self.urls[key]+('/history?since=0' if key=='central' else '/api/messages'))

    def close(self):
        if self.backend=='processes':
            for key in list(self.processes): self.stop(key)
        else:
            # Dejar el laboratorio utilizable después de la medición.
            self.start('b')
        for handle in self.handles: handle.close()
