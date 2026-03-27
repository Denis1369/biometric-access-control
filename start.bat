@echo off
chcp 65001 >nul
echo Запуск системы контроля доступа...

start "FastAPI Backend" cmd /k "cd backend && call .venv\Scripts\activate && uvicorn app.main:app --reload"

start "Vue Frontend" cmd /k "cd frontend && npm run dev"

echo Серверы успешно запущены в новых окнах!