@echo off
cd /d "%~dp0"
if not exist evidencias mkdir evidencias
docker compose exec -T grupo-a python -m unittest discover -s tests -v > evidencias\pruebas_en_docker.txt 2>&1
type evidencias\pruebas_en_docker.txt
pause
