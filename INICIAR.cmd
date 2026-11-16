@echo off
cd /d "%~dp0"
docker info >nul 2>&1
if errorlevel 1 (
 echo Abre Docker Desktop y espera a que el motor este listo. Luego vuelve a ejecutar este archivo.
 pause
 exit /b 1
)
docker compose up -d --build --wait
if errorlevel 1 (
 echo No fue posible iniciar. Copia el error visible para revisarlo.
 pause
 exit /b 1
)
start "" http://localhost:8001
start "" http://localhost:8002
echo Laboratorio iniciado: central simulado, grupo ga y grupo gb.
echo Para detener sin borrar datos: docker compose down
pause
