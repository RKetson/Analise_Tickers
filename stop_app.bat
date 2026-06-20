@echo off
title ValuacaoBR - Stop Services
color 0C

echo ==============================================================
echo Desligando Servicos do ValuacaoBR
echo ==============================================================
echo.
echo Tentando encerrar processos pythonw.exe rodando em segundo plano...
taskkill /F /IM pythonw.exe /T

echo.
echo Processo concluido. (Nota: Se houver terminais do modo debug abertos, voce precisara fecha-los manualmente).
echo ==============================================================
pause
