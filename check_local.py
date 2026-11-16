"""Pruebas propias. NO sustituye al script oficial de conformidad."""
import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4
from lab import Lab, request, wait_for

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--backend',choices=['processes','docker'],default='processes')
parser.add_argument('--output',default='evidencias/prueba_local')
args=parser.parse_args()
folder=Path(args.output).resolve()
folder.mkdir(parents=True,exist_ok=True)
lab=Lab(folder/'runtime',args.backend)
checks=[]
def passed(name):
    checks.append(name);print('PASS:',name,flush=True)
try:
    lab.boot();passed('Registro de ambos grupos y creación de usuarios')
    key=str(uuid4());m=lab.send('a','mensaje de integración',key)
    again=lab.send('a','mensaje de integración',key)
    assert again['id']==m['id'];passed('Idempotencia del cliente')
    wait_for(lambda:any(x['id']==m['id'] for x in lab.messages('b')))
    passed('Envío y recepción por HTTP entre tres procesos')
    clock=request(lab.urls['b']+'/fed/health')['lamport']
    request(lab.urls['b']+'/fed/messages','POST',{**m,'unknown':'ignorado'})
    assert request(lab.urls['b']+'/fed/health')['lamport']==clock
    assert sum(x['id']==m['id'] for x in lab.messages('b'))==1
    passed('Duplicado responde 200 sin modificar reloj ni historial; campos desconocidos ignorados')
    lab.stop('central')
    wait_for(lambda:request(lab.urls['a']+'/api/status')['central']=='offline',timeout=25)
    queued=lab.send('a','guardado con central caído')
    assert request(lab.urls['a']+'/api/status')['outbox']['pending']>=1
    lab.stop('a');lab.start('a')
    assert 'prueba' in request(lab.urls['a']+'/api/users')
    assert any(x['id']==queued['id'] for x in lab.messages('a'))
    passed('Heartbeat detecta caída; usuario, reloj, historial y cola sobreviven a cierre abrupto')
    lab.start('central')
    wait_for(lambda:any(x['id']==queued['id'] for x in lab.messages('b')),timeout=40)
    passed('Cola persistente se entrega al recuperarse el central')
    lab.stop('b');missed=lab.send('a','historial durante caída del receptor')
    wait_for(lambda:any(x['id']==missed['id'] for x in lab.messages('central')))
    lab.start('b')
    wait_for(lambda:any(x['id']==missed['id'] for x in lab.messages('b')))
    passed('Receptor recupera mensajes tras caída')
    # Inyectar mensaje tardío con Lamport bajo en el historial central.
    late={**m,'id':str(uuid4()),'lamport':1,'origin':'gc','from':'otro@gc','body':'evento tardío'}
    request(lab.urls['central']+'/messages','POST',late)
    wait_for(lambda:any(x['id']==late['id'] for x in lab.messages('b')))
    wait_for(lambda:{x['id'] for x in lab.messages('a')}=={x['id'] for x in lab.messages('b')})
    a=lab.messages('a');b=lab.messages('b')
    assert [x['id'] for x in a]==[x['id'] for x in b]
    assert [(x['lamport'],x['origin'],x['id']) for x in b]==sorted((x['lamport'],x['origin'],x['id']) for x in b)
    passed('Convergencia del historial y mismo orden, incluso con Lamport tardío bajo')
    (folder/'resultado.json').write_text(json.dumps({'scope':f'Pruebas propias, central simulado, backend {args.backend}',
        'checks':checks,'status':'PASS'},indent=2,ensure_ascii=False),encoding='utf-8')
finally:lab.close()
