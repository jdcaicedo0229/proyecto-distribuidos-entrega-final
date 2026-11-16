# Bitácora de validación e interoperabilidad local

Fecha de las pruebas: 11 de noviembre de 2026. Equipo anfitrión Windows 11, servicios Docker. El registro describe el laboratorio propio, no una sesión del curso con otros grupos.

| Actividad | Observación | Evidencia |
|---|---|---|
| Arranque | central, grupo-a y grupo-b reportaron healthy | Captura de docker compose ps aportada durante la validación |
| Conversación | Mensajes de ga visibles en gb y respuestas en sentido inverso | Comprobación manual confirmada; integración automática PASS |
| Reinicio de ga | Usuario e historial permanecieron | Confirmación manual; pruebas unitarias y de integración |
| Caída de gb | Mensajes enviados desde ga aparecieron al recuperar gb, sin duplicados visibles | Confirmación manual; integración PASS |
| Caída del central | Se conservaron pendientes; sobrevivieron al reinicio de ga y se entregaron al recuperar el central | Confirmación manual; integración PASS |
| Pruebas unitarias | 13 pruebas aprobadas en 0,776 s | evidencias/pruebas_en_docker.txt |
| Integración | Ocho comprobaciones aprobadas | evidencias/verificacion_docker/resultado.json |
| Experimento | Nueve ensayos; 360/360 mensajes; cero pérdidas y duplicados | resultados/mi_equipo/ |
| Revisión de medición | Objetivo 10 msg/s; observación agregada 0,479729 msg/s | send_timings de los JSON; análisis derivado |

## Hallazgos y tratamiento

El productor realiza solicitudes secuenciales. Los tiempos registrados muestran aproximadamente 2,08 s entre confirmaciones sucesivas; no se alcanzó la tasa objetivo. El informe reporta la carga observada y no atribuye esas esperas a una causa de red específica no medida.

La ventana tras reinicio incluye el final del productor y verificaciones posteriores. No se utiliza como latencia de mensajes ni como tiempo puro de recuperación.

La etiqueta “tres procesos” del resultado de integración es genérica; su campo scope identifica el backend docker. No se modificó el archivo original de evidencia.

## Interoperabilidad oficial

No consta conexión a un central oficial ni a implementaciones de otros equipos. No se recibió script de conformidad oficial. La prueba local demuestra funcionamiento entre instancias del mismo código. Una eventual sesión del curso debe registrarse con fecha, participantes, resultado, error observado y evidencia propia; no se completa retroactivamente como si hubiera ocurrido.
