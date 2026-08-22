@echo off
title Agente Manutenzione Predittiva
color 0A
echo.
echo  ============================================
echo   AGENTE MANUTENZIONE PREDITTIVA
echo   Server locale + Accesso da browser
echo  ============================================
echo.

set SCRIPT_DIR=%~dp0

echo  [1/2] Avvio server Streamlit...
start /b py -m streamlit run "%SCRIPT_DIR%app.py" --server.port 8501 --server.address 0.0.0.0 --server.headless true >nul 2>&1

timeout /t 4 /nobreak >nul

echo  [2/2] Apertura tunnel Cloudflare...
echo.
echo  ============================================
echo   Copia il link qui sotto e aprilo in browser
echo  ============================================
echo.

"%SCRIPT_DIR%cloudflared.exe" tunnel --url http://localhost:8501
