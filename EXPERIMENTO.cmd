@echo off
cd /d "%~dp0"
py -3 --version
if errorlevel 1 (
 echo Instala Python 3 desde python.org y habilita el lanzador py. Consulta la guia.
 pause
 exit /b 1
)
echo Se apagara el receptor gb varias veces. No uses el laboratorio durante la medicion.
py -3 scripts\experiment.py --backend docker --output resultados\mi_equipo
pause
