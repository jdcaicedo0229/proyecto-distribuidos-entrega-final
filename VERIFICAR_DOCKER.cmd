@echo off
cd /d "%~dp0"
py -3 scripts\check_local.py --backend docker --output evidencias\verificacion_docker
pause
