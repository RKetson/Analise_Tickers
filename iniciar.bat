@echo off
title Analise de Tickers Dashboard
cd /d "%~dp0"

echo ===================================================
echo   Iniciando o Dashboard de Analise de Tickers...
echo ===================================================
echo.

IF NOT EXIST ".venv\Scripts\activate.bat" (
    echo [AVISO] Ambiente virtual .venv nao encontrado!
    echo Criando ambiente virtual...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo Instalando dependencias...
    pip install -r requirements.txt
) ELSE (
    call .venv\Scripts\activate.bat
)

echo.
echo Executando a aplicacao...
streamlit run app.py

pause
