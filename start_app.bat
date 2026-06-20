@echo off
title ValuacaoBR - Launcher
color 0A

echo ==============================================================
echo Iniciando Servicos do ValuacaoBR 2.0.0
echo ==============================================================
echo.

SET DEBUG_MODE=0
IF "%~1"=="debug" SET DEBUG_MODE=1
IF "%~1"=="--debug" SET DEBUG_MODE=1

IF %DEBUG_MODE%==1 (
    echo [MODO DEBUG] Os terminais ficarao visiveis para inspecao de logs.
    echo.
    echo [1/2] Iniciando Backend FastAPI (Pluggy)...
    cd API_pluggy
    start "FastAPI Backend (Pluggy)" cmd /k "..\.venv\Scripts\activate && uvicorn main:app --reload --port 8000"
    cd ..

    echo Aguardando o backend inicializar (3 segundos)...
    timeout /t 3 /nobreak >nul

    echo [2/2] Iniciando Frontend Streamlit...
    start "Streamlit Frontend" cmd /k ".venv\Scripts\activate && streamlit run app.py"
) ELSE (
    echo [MODO SILENCIOSO] Os servicos rodarao em segundo plano (background).
    echo Para ver os logs ou diagnosticar problemas, execute: start_app.bat debug
    echo Para desligar a aplicacao depois, execute: stop_app.bat
    echo.
    
    echo [1/2] Iniciando Backend FastAPI (Pluggy)...
    cd API_pluggy
    start "" "..\.venv\Scripts\pythonw.exe" -m uvicorn main:app --port 8000
    cd ..

    echo Aguardando o backend inicializar (3 segundos)...
    timeout /t 3 /nobreak >nul

    echo [2/2] Iniciando Frontend Streamlit...
    start "" ".venv\Scripts\pythonw.exe" -m streamlit run app.py
)

echo.
echo ==============================================================
echo Servicos iniciados com sucesso!
echo - Streamlit: http://localhost:8501
echo - FastAPI  : http://localhost:8000
echo ==============================================================

IF %DEBUG_MODE%==0 (
    echo Fechando este terminal em 5 segundos...
    timeout /t 5 /nobreak >nul
) ELSE (
    pause
)
