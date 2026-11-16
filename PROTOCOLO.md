# Contrato HTTP y decisiones de implementación

El sistema sigue las rutas y reglas del resumen del enunciado UIS. La especificación externa y el script oficial mencionados en ese documento no fueron suministrados. El contrato descrito aquí es local y su compatibilidad con un central oficial no está certificada.

## Rutas de federación

| Servicio | Ruta | Función |
|---|---|---|
| Central | POST /register | Registro o renovación de {server, url} |
| Central | POST /messages | Ingreso idempotente del mensaje |
| Central | GET /history?since=L | Mensajes con Lamport mayor que L |
| Central | GET /health | Disponibilidad del central |
| Grupo | POST /fed/messages | Recepción idempotente |
| Grupo | GET /fed/health | Nombre del servidor y reloj actual |

Campos de mensaje: id (UUID), from, origin, lamport, sent_at y body. Los campos desconocidos se ignoran. Un duplicado por ID responde HTTP 200 sin modificar historial ni reloj. El central reenvía a los grupos registrados salvo al de origen. El mensaje propio se almacena antes de enviarse.

## Decisiones locales

| Aspecto | Decisión |
|---|---|
| Respuesta de historial | Lista JSON; adaptador acepta también un objeto con messages |
| Reconciliación | since=0 al arrancar, al recuperarse el central y cada 5 s |
| Paginación | El simulador no pagina; el adaptador rechaza señales de páginas adicionales no soportadas |
| Respuestas de registro y entrega | HTTP 200 y status=ok |
| Salud de grupo | server y lamport |
| Registro del simulador | Caduca a los 30 s; los grupos renuevan cada 10 s |
| Heartbeat | Cada 2 s; umbral de tres fallos; timeout configurado de 3 s |
| Reintento | Backoff nominal 1, 2, 4... hasta 30 s; multiplicador aleatorio entre 0,8 y 1 |
| Error 4xx de mensaje | Estado rejected, sin reintento automático |
| Error 4xx de registro/historial | Se bloquea esa operación hasta corregir y reiniciar |
| Orden | Lamport, origen y UUID como desempate final |
| Persistencia | SQLite en volumen; un worker por servicio |

Recibir una marca Lamport alta no demuestra que no falten marcas menores. La reconciliación completa evita usar el reloj local como cursor de completitud, a cambio de transferir repetidamente el historial. La marca del mensaje no cambia durante reintentos ni recepciones.

## API del cliente

GET /api/users y POST /api/users consultan y crean alias. GET /api/messages devuelve historial con estados de entrega. POST /api/messages recibe username, body y request_id; responde 202 al encolar. Repetir la misma clave y contenido conserva el mensaje. Cambiar contenido con esa clave responde 409. GET /api/status expone conexión, reloj y cantidades de la cola.

La clave del cliente y el UUID federado son distintos. El navegador conserva su clave al reintentar sin recargar la página; no se promete deduplicar un envío manual nuevo después de una recarga. El estado sent solo confirma recepción central.

## Límites

Servicios para laboratorio, sin autenticación fuerte ni cifrado de aplicación. No hay consenso ni replicación del central. La convergencia del historial depende de disponer finalmente del mismo conjunto de mensajes; una recepción tardía puede insertar mensajes antes de otros ya visibles. Entrega al menos una vez y procesamiento idempotente no equivalen a una garantía general de exactamente una vez extremo a extremo.

Esquemas locales: openapi_grupo_local.json y openapi_central_simulado.json. En ejecución: /openapi.json y /docs de cada servicio.
