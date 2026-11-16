# Índice de capturas técnicas

Nueve imágenes originales aportadas para documentar la ejecución local. Se conservan sin editar; los nombres se normalizan y el índice JSON conserva el nombre original y su SHA-256. El orden es expositivo, no una cronología deducida de los números originales.

## 1. Entorno Docker y comienzo de construcción

Archivo: 01_entorno_docker.jpeg. Original: cortejo 3.jpeg.

Docker Desktop sobre WSL2 y ejecución de docker compose up. La captura identifica el entorno; no acredita por sí sola que el chat haya terminado de arrancar.

## 2. Construcción y salud de los servicios

Archivo: 02_servicios_saludables.jpeg. Original: cortejo 2.jpeg.

Aparecen central, grupo-a y grupo-b como healthy, con puertos locales 8000, 8001 y 8002. También se observa creación de red y volúmenes.

## 3. Envío desde ga

Archivo: 03_envio_ga.jpeg. Original: cortejo 1.jpeg.

El cliente de ga muestra Hola desde el grupo ga, Lamport 1 y estado Enviado al central. Este estado no confirma lectura por el destinatario.

## 4. Recepción y respuesta en gb

Archivo: 04_respuesta_gb.jpeg. Original: cortejo 4.jpeg.

gb muestra el mensaje remoto de ga y una respuesta propia. Los colores distinguen origen local y remoto.

## 5. Reinicio y caída controlada

Archivo: 05_caida_controlada.jpeg. Original: cortejo 5.jpeg.

Se observa docker compose restart grupo-a y docker compose kill grupo-b. La imagen registra acciones de fallo; no demuestra sola la recuperación posterior.

## 6. Historial visible en gb

Archivo: 06_historial_recuperado.jpeg. Original: cortejo 6.jpeg.

El cliente gb presenta PRUEBA DE PERSISTENCIA y Durante la caída 1, 2 y 3. Se interpreta junto a las acciones previas y las pruebas automáticas; no mide latencias.

## 7. Pruebas unitarias aprobadas

Archivo: 07_pruebas_unitarias.jpeg. Original: cortejo 7.jpeg.

La consola muestra Ran 13 tests in 0.766s y OK. Los eventos retry y errores simulados forman parte de los casos de prueba y no significan que la batería haya fallado.

## 8. Archivo de la salida de pruebas

Archivo: 08_guardado_evidencia.jpeg. Original: cortejo 8.jpeg.

Se observa el comando que vuelve a ejecutar las pruebas redirigiendo su salida a evidencias/pruebas_en_docker.txt, y su apertura con Notepad. La salida anterior visible repite la ejecución de la captura 07; no se cuenta como 13 casos adicionales.

## 9. Verificación de integración

Archivo: 09_integracion_docker.jpeg. Original: cortejo 9.jpeg.

Se observa Python 3.14.3, ejecución de check_local.py con backend docker y comprobaciones PASS de registro, idempotencia, comunicación, duplicados y recuperación. La imagen no muestra el final completo; las ocho comprobaciones se respaldan con verificacion_docker/resultado.json.

Las capturas 07 y 08 muestran la misma salida visible de 0,766 s. El TXT archivado corresponde a otra ejecución, de 0,776 s. No se suman como 26 casos: la batería tiene 13 pruebas. Ninguna imagen muestra una conversación con IA. Su inclusión en el registro de IA documenta la validación del resultado asistido.
