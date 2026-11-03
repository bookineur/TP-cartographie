@echo off
rem Double-cliquer pour lancer Lidar Plot (visualiseur temps reel du LD06).
cd /d "%~dp0"
python -m carto plot
if errorlevel 1 (
    echo.
    echo Erreur au lancement. Verifier : pip install -r requirements.txt
    pause
)
