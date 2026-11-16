# Chat distribuido con recuperación ante fallos

Proyecto de Sistemas Distribuidos, UIS. Implementación de un servidor de grupo con cliente web y persistencia, acompañado de un central simulado para pruebas locales. La sala compartida es `#general`.

## Ejecución en un equipo limpio

Requisitos: Docker Engine o Docker Desktop con Docker Compose v2. La primera construcción necesita Internet para descargar la imagen base y las dependencias. Para los scripts externos de medición se requiere Python 3; su modo Docker utiliza la biblioteca estándar y no exige instalar los paquetes del servidor en Windows.

Desde la carpeta que contiene `docker-compose.yml`:

```bash
docker compose up -d --build --wait
docker compose ps
```

También puede arrancarse en primer plano con `docker compose up`. El archivo construye tres servicios y sus volúmenes. Los clientes son:

| Servicio | Dirección en el equipo |
|---|---|
| Grupo ga | http://localhost:8001 |
| Grupo gb | http://localhost:8002 |
| API del central simulado | http://localhost:8000/docs |

En cada cliente se crea un alias, se selecciona el usuario y se envían mensajes. Los mensajes del grupo local y los externos se distinguen por color. El estado `pending` significa guardado localmente; `sent` confirma recepción del central, no lectura por otros usuarios.

Para detener sin eliminar datos: `docker compose down`. Los volúmenes persisten. `docker compose down -v` elimina los datos y no forma parte del procedimiento de recuperación.

## Pruebas y reproducción

```bash
docker compose exec -T grupo-a python -m unittest discover -s tests -v
python scripts/check_local.py --backend docker --output evidencias/verificacion_nueva
python scripts/experiment.py --backend docker --output resultados/ejecucion_nueva
python scripts/analizar_resultados.py --results resultados/ejecucion_nueva
```

En Windows se puede usar `py -3` en lugar de `python`. Las pruebas de integración y el experimento apagan y reinician deliberadamente servicios del laboratorio. Ejecutarlas sin mensajes manuales simultáneos. Cada experimento debe usar una carpeta de salida nueva para conservar las ejecuciones previas.

El experimento realiza tres repeticiones por duración configurada de caída (1, 2 y 3 s), con 40 mensajes por ensayo. La tasa objetivo predeterminada es 10 mensajes/s; la tasa observada debe calcularse a partir de los tiempos registrados. El generador es secuencial y no garantiza alcanzar el objetivo.

## Resultados incluidos

Los datos de `resultados/mi_equipo/` proceden del equipo anfitrión: Windows 11, generador Python 3.14.3 y servicios Docker. En nueve ensayos se recuperaron 360/360 mensajes, sin faltantes ni duplicados visibles. La tasa efectiva agregada fue 0,479729 mensajes/s. No se interpreta como rendimiento máximo ni como prueba a 10 mensajes/s.

Evidencias: `evidencias/pruebas_en_docker.txt` contiene 13 pruebas aprobadas; `evidencias/verificacion_docker/resultado.json` contiene ocho comprobaciones aprobadas. Son pruebas propias con central simulado, no la salida de un script oficial de conformidad.

## Configuración

| Variable | Valor predeterminado | Propósito |
|---|---|---|
| GROUP_ID | ga / gb en laboratorio | Identidad del servidor |
| CENTRAL_URL | http://central:8000 en laboratorio | Dirección del central |
| PUBLIC_URL | http://grupo-a:8000 / http://grupo-b:8000 | Dirección anunciada al central |
| DB_PATH | /data/group.db | Base persistente |
| HEARTBEAT_INTERVAL | 2 s | Intervalo de comprobación |
| FAILURE_THRESHOLD | 3 | Fallos consecutivos para sospechar caída |
| REGISTER_INTERVAL | 10 s | Renovación de registro |
| SYNC_INTERVAL | 5 s | Reconciliación de historial |
| HTTP_TIMEOUT | 3 s | Timeout de operaciones HTTPX |
| RETRY_BASE | 1 s | Espera nominal inicial |
| RETRY_MAX | 30 s | Tope nominal de backoff |
| PORT | 8001 en modo curso | Puerto del equipo |

Los valores del laboratorio están declarados en `docker-compose.yml`. El modo de conexión externa usa `.env.curso.example`, que se copia a `.env.curso` y se completa con datos reales:

```bash
docker compose --env-file .env.curso -f compose.curso.yml up -d --build --wait
```

Este modo levanta únicamente el servidor de grupo. `PUBLIC_URL` debe ser accesible desde el central; `localhost` no identifica al portátil desde otro equipo. El puerto 8001 debe estar libre, por lo que no se ejecutan ambos modos simultáneamente con el mismo puerto. La conexión al central oficial y a servidores de otros equipos no se ha verificado.

## Diseño

- Estrella: los grupos intercambian mensajes a través del central.
- Un worker por servidor; SQLite local con WAL y transacciones.
- Persistencia conjunta de reloj, mensaje, cola de envío y clave idempotente del cliente.
- UUID del mensaje estable durante los reintentos; duplicados recibidos sin efectos.
- Reintentos de 5xx y fallos de red con backoff exponencial y jitter. Los 4xx son terminales según el enunciado.
- Lamport: incremento al crear un evento; máximo local/recibido más uno al recibir uno nuevo. Orden por Lamport, origen e ID como desempate adicional.
- Reconciliación completa con `GET /history?since=0`. Evita omitir eventos tardíos con marca inferior al máximo visto; tiene costo creciente y no implementa paginación.
- Cliente con consulta periódica cada segundo; alias sin autenticación fuerte. Uso previsto: laboratorio académico controlado.

El resumen del protocolo del enunciado es la referencia disponible. Las decisiones adicionales y las respuestas locales están en `docs/PROTOCOLO.md`. El OpenAPI generado corresponde exclusivamente a esta implementación.

## Contenido

| Ruta | Contenido |
|---|---|
| app/ | Servidor de grupo, persistencia, modelos y central simulado |
| static/ | Cliente web |
| scripts/ | Integración, experimento y análisis de resultados |
| tests/ | Pruebas unitarias |
| resultados/mi_equipo/ | Nueve ensayos originales y análisis derivados |
| evidencias/ | Salidas de pruebas Docker e integridad de archivos |
| docs/INFORME_TECNICO.pdf | Diseño, método, resultados, discusión y referencias |
| docs/ARQUITECTURA.md y docs/figuras/ | Diagrama de servicios, red y volúmenes |
| docs/BITACORA.md | Bitácora de validación local y alcance de interoperabilidad |
| docs/ESTADO_REQUISITOS.md | Trazabilidad de requisitos y evidencias |
| docs/uso_ia/ | Registro separado del uso de IA |
| docs/POSTER.pdf | Póster final A1 vertical |

La reproducción de las estadísticas y figuras requiere `python -m pip install -r requirements-docs.txt` y `python scripts/generar_estadisticas.py`. Estas dependencias no son necesarias para arrancar el chat. Los informes y el póster se entregan en sus versiones finales PDF.

## Alcance de entrega

Las verificaciones incluidas acreditan el laboratorio propio. No se dispone de salida oficial de conformidad ni de una sesión entre implementaciones de distintos grupos. El registro de IA incluye nueve capturas técnicas comentadas. El póster final está incluido en `docs/POSTER.pdf` (A1 vertical). La participación individual debe acreditarse con contribuciones reales y su historial de commits.


## Identificación del equipo

| Integrante | Código |
|---|---|
| Juan Diego Caicedo Ortiz | 2252921 |
| Diego Alejandro Villamizar | 2252898 |
| Juan Felipe Herrera Arias | 2252920 |
| Luis David Pocaterra Puello | 2252919 |
| Juan Pablo Galvis Cañon | 2253477 |

Los identificadores ga y gb corresponden a instancias del laboratorio, no al identificador oficial del equipo.
