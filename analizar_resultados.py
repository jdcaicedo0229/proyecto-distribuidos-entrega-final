"""Auditoría reproducible de UUID y tasa efectiva; no modifica los datos originales."""
import csv,json,statistics,argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--results',default='resultados/mi_equipo');a=p.parse_args()
f=Path(a.results);rows=[]
for r in csv.DictReader((f/'resumen.csv').open(encoding='utf-8')):
 d=json.loads((f/(r['ensayo']+'.json')).read_text(encoding='utf-8'))
 sent={m['id'] for m in d['sent']};got=[m['id'] for m in d['received'] if m['body'].startswith(r['ensayo'])]
 t=d['send_timings'];duration=t[-1]['elapsed_s'];intervals=[b['elapsed_s']-a['elapsed_s'] for a,b in zip(t,t[1:])]
 rows.append(dict(ensayo=r['ensayo'],caida_s=r['caida_configurada_s'],repeticion=r['repeticion'],enviados=len(sent),recibidos=len(sent&set(got)),perdidos=len(sent-set(got)),duplicados=len(got)-len(set(got)),duracion_productor_s=round(duration,6),tasa_observada_msg_s=round(len(sent)/duration,6),intervalo_medio_s=round(statistics.mean(intervals),6),indisponibilidad_observada_s=r['indisponibilidad_observada_s']))
 print(r['ensayo'],rows[-1]['recibidos'],'recibidos;',rows[-1]['tasa_observada_msg_s'],'msg/s observados')
with (f/'analisis_verificado.csv').open('w',newline='',encoding='utf-8') as out:
 w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
