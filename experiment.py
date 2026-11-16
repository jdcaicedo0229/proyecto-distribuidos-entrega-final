"""Pérdidas ante caída: tres repeticiones por duración; datos y evidencias reales."""
import argparse
import csv
import json
import platform
import threading
import time
import traceback
from pathlib import Path
from uuid import uuid4
from lab import Lab, wait_for

def run_trial(lab, duration, count, rate, tag, folder):
    expected=[]
    errors=[]
    timings=[]
    def produce():
        start=time.monotonic()
        for i in range(count):
            target=start+i/rate
            time.sleep(max(0,target-time.monotonic()))
            try:
                msg=lab.send('a',f'{tag} mensaje {i+1}')
                expected.append(msg)
                timings.append({'index':i+1,'elapsed_s':time.monotonic()-start,'id':msg['id']})
            except Exception as exc: errors.append(str(exc))
    thread=threading.Thread(target=produce)
    thread.start()
    time.sleep(.5)
    start_down=time.monotonic()
    lab.stop('b')
    time.sleep(duration)
    restart=time.monotonic()
    lab.start('b')
    available=time.monotonic()
    thread.join()
    if errors: raise RuntimeError(f'Falló generador: {errors}')
    ids={x['id'] for x in expected}
    wait_for(lambda:ids.issubset({x['id'] for x in lab.messages('central')}))
    converged=True
    try:
        wait_for(lambda:ids.issubset({x['id'] for x in lab.messages('b')}),timeout=40)
    except TimeoutError:
        converged=False
    observed=time.monotonic()
    central=lab.messages('central')
    received=lab.messages('b')
    relevant=[m for m in received if m['body'].startswith(tag)]
    actual={m['id'] for m in relevant}
    missing=ids-actual
    unexpected=actual-ids
    duplicates=len(relevant)-len(actual)
    (folder/f'{tag}.json').write_text(json.dumps({'sent':expected,'central':central,'received':received,
        'send_timings':timings,'missing_ids':sorted(missing),'unexpected_ids':sorted(unexpected),
        'converged':converged},ensure_ascii=False,indent=2),encoding='utf-8')
    return {'ensayo':tag,'caida_configurada_s':duration,'repeticion':int(tag.split('-')[1]),
        'enviados':len(expected),'recibidos_unicos':len(actual & ids),'perdidos':len(missing),
        'duplicados':duplicates,'inesperados':len(unexpected),'tasa_objetivo_msg_s':rate,
        'indisponibilidad_observada_s':round(available-start_down,4),
        'ventana_verificacion_tras_reinicio_s':round(observed-restart,4),
        'convergio':converged}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend',choices=['processes','docker'],default='processes')
    p.add_argument('--output',default='resultados/mi_equipo')
    p.add_argument('--durations',nargs='+',type=float,default=[1,2,3])
    p.add_argument('--repetitions',type=int,default=3)
    p.add_argument('--count',type=int,default=40)
    p.add_argument('--rate',type=float,default=10)
    args=p.parse_args()
    if args.rate<=0 or args.repetitions<3 or min(args.durations)<=0:
        p.error('Tasa y duración positivas; al menos tres repeticiones')
    if (args.count-1)/args.rate <= .5+max(args.durations):
        p.error('Aumenta count: debe haber envíos antes, durante y después de la caída')
    folder=Path(args.output).resolve()
    if (folder/'resumen.csv').exists(): p.error('La carpeta ya tiene resultados: usa otra ruta para conservarlos')
    folder.mkdir(parents=True,exist_ok=True)
    lab=Lab(folder/'runtime',args.backend)
    meta={'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
          'python':platform.python_version(),'platform':platform.platform(),
          'backend':args.backend,'central':'simulador local; NO servidor oficial',
          'parameters':vars(args),'notes':'Caída abrupta del proceso o contenedor receptor. Sincronización completa periódica.'}
    (folder/'metadatos.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    rows=[]
    try:
        lab.boot()
        for duration in args.durations:
            for repetition in range(1,args.repetitions+1):
                tag=f'{duration:g}s-{repetition}-{uuid4().hex[:6]}'
                print(f'Midiendo {duration:g}s de caída, repetición {repetition}/{args.repetitions}',flush=True)
                row=run_trial(lab,duration,args.count,args.rate,tag,folder)
                rows.append(row)
                with open(folder/'resumen.csv','w',newline='',encoding='utf-8') as f:
                    writer=csv.DictWriter(f,fieldnames=list(row));writer.writeheader();writer.writerows(rows)
                print(f"  Faltantes: {row['perdidos']}; duplicados: {row['duplicados']}",flush=True)
    except Exception:
        (folder/'ERROR.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
    finally: lab.close()
    # Gráfica SVG autónoma; escala de conteos común, etiquetas incluso con ceros.
    bars=[]
    max_value=max(1,max(max(r['perdidos'],r['duplicados']) for r in rows))
    for i,row in enumerate(rows):
        x=70+i*82
        for offset,key,color in [(0,'perdidos','#d65d43'),(27,'duplicados','#784ab7')]:
            value=row[key];height=value/max_value*190
            bars.append(f'<rect x="{x+offset}" y="{260-height}" width="23" height="{max(height,1)}" fill="{color}"/>')
            bars.append(f'<text x="{x+offset+11}" y="{249-height}" text-anchor="middle">{value}</text>')
        bars.append(f'<text x="{x+23}" y="285" text-anchor="middle">{row["caida_configurada_s"]:g}s / R{row["repeticion"]}</text>')
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{max(850,len(rows)*82+100)}" height="350">
    <rect width="100%" height="100%" fill="white"/><g font-family="sans-serif" font-size="13" fill="#21344a">
    <text x="30" y="30" font-size="20">Pérdidas y duplicados tras recuperación · laboratorio local</text>
    <text x="30" y="55">Conteo de mensajes · naranja: perdidos · morado: duplicados</text>
    <path d="M50 70 V260 H{len(rows)*82+80}" fill="none" stroke="#64748b"/>
    <text x="25" y="265">0</text><text x="25" y="75">{max_value}</text>{''.join(bars)}
    <text x="30" y="330">Cada ensayo: {args.count} mensajes; tasa objetivo: {args.rate:g} msg/s. La tasa observada se calcula con send_timings.</text></g></svg>'''
    (folder/'grafica.svg').write_text(svg,encoding='utf-8')
    print(f'Resultados guardados en {folder}',flush=True)

if __name__=='__main__': main()
