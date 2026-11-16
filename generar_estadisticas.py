"""Verifica datos originales y genera estadísticas descriptivas y figuras."""
import csv,json,statistics,hashlib,argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,Rectangle
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--results',default='resultados/mi_equipo');args=parser.parse_args()
    folder=Path(args.results)
    if not folder.is_absolute():folder=ROOT/folder
    source=list(csv.DictReader((folder/'resumen.csv').open(encoding='utf-8')));rows=[];hashes={}
    for r in source:
        path=folder/(r['ensayo']+'.json');d=json.loads(path.read_text(encoding='utf-8'))
        sent=[m['id'] for m in d['sent']];recv=[m['id'] for m in d['received'] if m['body'].startswith(r['ensayo'])]
        expected=set(sent);actual=set(recv);timing=d['send_timings']
        if len(sent)!=len(expected):raise ValueError('IDs repetidos en origen')
        if {t['id'] for t in timing}!=expected:raise ValueError('Tiempos y mensajes no coinciden')
        lost=len(expected-actual);dup=len(recv)-len(actual);unexpected=len(actual-expected)
        if (lost,dup,unexpected)!=(int(r['perdidos']),int(r['duplicados']),int(r['inesperados'])):raise ValueError('CSV y JSON difieren')
        elapsed=timing[-1]['elapsed_s']
        rows.append({'ensayo':r['ensayo'],'caida_s':float(r['caida_configurada_s']),
            'repeticion':int(r['repeticion']),'enviados':len(sent),'recibidos':len(expected&actual),
            'perdidos':lost,'duplicados':dup,'inesperados':unexpected,
            'duracion_productor_s':elapsed,'tasa_observada_msg_s':len(sent)/elapsed,
            'indisponibilidad_observada_s':float(r['indisponibilidad_observada_s']),
            'ventana_verificacion_s':float(r['ventana_verificacion_tras_reinicio_s'])})
        hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    summaries=[]
    for duration in sorted({r['caida_s'] for r in rows}):
        group=[r for r in rows if r['caida_s']==duration]
        summary={'caida_configurada_s':duration,'repeticiones':len(group)}
        for key in ['enviados','recibidos','perdidos','duplicados','inesperados']:summary[key]=sum(r[key] for r in group)
        for key in ['duracion_productor_s','tasa_observada_msg_s','indisponibilidad_observada_s','ventana_verificacion_s']:
            values=[r[key] for r in group];summary[key+'_media']=statistics.mean(values);summary[key+'_desv_muestral']=statistics.stdev(values)
        summaries.append(summary)
    total=sum(r['enviados'] for r in rows)
    aggregate={'ensayos':len(rows),'enviados':total,'recibidos':sum(r['recibidos'] for r in rows),
        'perdidos':sum(r['perdidos'] for r in rows),'duplicados':sum(r['duplicados'] for r in rows),
        'tasa_agregada_msg_s':total/sum(r['duracion_productor_s'] for r in rows),
        'duracion_productor_media_s':statistics.mean(r['duracion_productor_s'] for r in rows),
        'duracion_productor_desv_muestral_s':statistics.stdev(r['duracion_productor_s'] for r in rows),
        'tasa_media_msg_s':statistics.mean(r['tasa_observada_msg_s'] for r in rows),
        'tasa_desv_muestral_msg_s':statistics.stdev(r['tasa_observada_msg_s'] for r in rows)}
    (folder/'estadisticas.json').write_text(json.dumps({'agregado':aggregate,'por_condicion':summaries,'ensayos':rows},indent=2,ensure_ascii=False),encoding='utf-8')
    with (folder/'estadisticas_por_condicion.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
    for path in [folder/'resumen.csv',folder/'metadatos.json',ROOT/'evidencias/pruebas_en_docker.txt',ROOT/'evidencias/verificacion_docker/resultado.json']:
        hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    (ROOT/'evidencias/integridad_datos.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    figdir=ROOT/'docs/figuras';figdir.mkdir(exist_ok=True,parents=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(11.6,4.4),layout='constrained')
    labels=[f"{r['caida_s']:g}s R{r['repeticion']}" for r in rows]
    axes[0].bar(range(len(rows)),[r['recibidos'] for r in rows],color='#197c8c');axes[0].set_xticks(range(len(rows)),labels,rotation=45,ha='right')
    axes[0].set_ylim(0,47);axes[0].set_ylabel('Mensajes recuperados');axes[0].set_title('40 de 40 en cada ensayo')
    for i in range(len(rows)):axes[0].text(i,41,'40',ha='center',fontsize=9)
    axes[1].plot(range(len(rows)),[r['perdidos'] for r in rows],'o',label='Faltantes',color='#c85034',markersize=9)
    axes[1].plot(range(len(rows)),[r['duplicados'] for r in rows],'x',label='Duplicados visibles',color='#173a5c',markersize=8)
    axes[1].set_xticks(range(len(rows)),labels,rotation=45,ha='right');axes[1].set_ylim(-.25,1);axes[1].set_yticks([0,1]);axes[1].set_title('Cero faltantes y duplicados');axes[1].set_ylabel('Conteo de mensajes');axes[1].legend(loc='upper right')
    fig.suptitle('Recuperación tras caída del receptor · Docker local')
    for suffix in ['png','svg']:fig.savefig(figdir/f'recuperacion.{suffix}',dpi=180)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11.6,4.4),layout='constrained')
    axes[0].bar(['Objetivo','Observada'],[10,aggregate['tasa_agregada_msg_s']],color=['#a9b8c9','#197c8c']);axes[0].set_ylabel('Mensajes/s');axes[0].set_ylim(0,11.5);axes[0].set_title('El objetivo no se alcanzó')
    axes[0].text(0,10.25,'10,00',ha='center');axes[0].text(1,.75,'0,48',ha='center')
    axes[1].errorbar([1,2,3],[s['indisponibilidad_observada_s_media'] for s in summaries],yerr=[s['indisponibilidad_observada_s_desv_muestral'] for s in summaries],fmt='o-',capsize=5,color='#197c8c',label='Media ± desv. muestral; n=3')
    axes[1].plot([1,2,3],[1,2,3],'--',color='#8b96a2',label='Espera configurada');axes[1].set_xticks([1,2,3]);axes[1].set_xlabel('Caída configurada (s)');axes[1].set_ylabel('Indisponibilidad observada (s)');axes[1].set_ylim(0,7.5);axes[1].legend(fontsize=9);axes[1].set_title('Incluye apagado y arranque')
    for suffix in ['png','svg']:fig.savefig(figdir/f'condiciones_medicion.{suffix}',dpi=180)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(11.6,6));ax.set_xlim(0,12);ax.set_ylim(0,8.6);ax.axis('off')
    ax.add_patch(Rectangle((.3,.6),11.4,5.9,fill=False,edgecolor='#8ca4b5',linewidth=1.4))
    ax.text(.5,6.15,'Red interna de Docker Compose · chat-distribuido-lab',fontsize=12,color='#173a5c')
    def box(x,y,w,h,text,color='#e9f2f5'):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.08',facecolor=color,edgecolor='#829aa9'))
        ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=11)
    box(.6,7,2.7,1,'Cliente web A\nlocalhost:8001');box(8.7,7,2.7,1,'Cliente web B\nlocalhost:8002')
    box(.6,3.9,2.7,1.5,'grupo-a · ga\nFastAPI :8000\napp.group')
    box(4.6,3.9,2.8,1.5,'central simulado\nFastAPI :8000\napp.central_mock')
    box(8.7,3.9,2.7,1.5,'grupo-b · gb\nFastAPI :8000\napp.group')
    for x,label in [(.6,'a-data\nSQLite /data/group.db'),(4.6,'central-data\nSQLite /data/central.db'),(8.7,'b-data\nSQLite /data/group.db')]:box(x,1.25,2.7,1.15,label,'#f1f4f8')
    def arrow(x1,y1,x2,y2,both=False):ax.annotate('',xy=(x2,y2),xytext=(x1,y1),arrowprops={'arrowstyle':'<->' if both else '->','color':'#197c8c','lw':1.8})
    arrow(1.95,7,1.95,5.4);arrow(10.05,7,10.05,5.4);arrow(3.4,4.65,4.5,4.65,True);arrow(7.5,4.65,8.6,4.65,True)
    for x in [1.95,6,10.05]:arrow(x,3.9,x,2.4)
    ax.text(4,4.95,'HTTP/JSON',ha='center',fontsize=9);ax.text(8.05,4.95,'HTTP/JSON',ha='center',fontsize=9)
    ax.text(6,.15,'Volúmenes independientes · sin comunicación directa entre grupos',ha='center',fontsize=11)
    for suffix in ['png','svg']:fig.savefig(figdir/f'arquitectura.{suffix}',dpi=180,bbox_inches='tight')
    plt.close(fig)
    print(json.dumps(aggregate,indent=2))
if __name__=='__main__':main()
