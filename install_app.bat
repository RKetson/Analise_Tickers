@echo off
title ValuacaoBR - Instalador
color 0B

echo ==============================================================
echo Iniciando a Instalacao do ValuacaoBR 2.0.0
echo ==============================================================
echo.

echo [1/4] Verificando Python...
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERRO] O Python nao foi encontrado no PATH. Por favor instale o Python 3.11+ e tente novamente.
    pause
    exit /b 1
)

echo [2/4] Criando Ambiente Virtual (.venv)...
IF NOT EXIST .venv (
    python -m venv .venv
    echo Ambiente Virtual criado com sucesso.
) ELSE (
    echo O Ambiente Virtual (.venv) ja existe.
)

echo.
echo [3/4] Instalando dependencias do Frontend (Streamlit)...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

echo.
echo [4/4] Instalando dependencias do Backend (FastAPI/Pluggy)...
cd API_pluggy
..\.venv\Scripts\python.exe -m pip install -r requirements.txt

IF NOT EXIST .env (
    echo Criando arquivo .env basico...
    copy .env.example .env >nul
    echo [AVISO] Arquivo .env criado em API_pluggy\.env. Lembre-se de preencher suas chaves do Pluggy.ai!
) ELSE (
    echo Arquivo .env ja existe em API_pluggy.
)
cd ..

echo.
echo ==============================================================
echo Instalacao concluida com sucesso!
echo Execute "start_app.bat" para iniciar o projeto.
echo ==============================================================
pause
