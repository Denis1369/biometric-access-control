@echo off
chcp 65001 >nul
setlocal
echo Запуск системы контроля доступа...

set "PORT_CACHE=%TEMP%\biometric_access_ports_%RANDOM%_%RANDOM%.txt"
netstat -ano > "%PORT_CACHE%"

if not defined BACKEND_PORT call :find_free_port BACKEND_PORT 8000 8010
if not defined FRONTEND_PORT call :find_free_port FRONTEND_PORT 5173 5183

if not defined BACKEND_PORT (
  del "%PORT_CACHE%" >nul 2>nul
  echo Не удалось найти свободный порт для backend в диапазоне 8000-8010.
  pause
  exit /b 1
)

if not defined FRONTEND_PORT (
  del "%PORT_CACHE%" >nul 2>nul
  echo Не удалось найти свободный порт для frontend в диапазоне 5173-5183.
  pause
  exit /b 1
)

del "%PORT_CACHE%" >nul 2>nul

set "API_BASE_URL=http://localhost:%BACKEND_PORT%/api"
set "CORS_ALLOW_ORIGINS=http://localhost:%FRONTEND_PORT%,http://127.0.0.1:%FRONTEND_PORT%"

echo Backend:  http://127.0.0.1:%BACKEND_PORT%
echo Frontend: http://127.0.0.1:%FRONTEND_PORT%

if "%DRY_RUN%"=="1" (
  echo DRY_RUN включен: серверы не запускаются.
  endlocal
  goto :eof
)

start "FastAPI Backend" cmd /k "cd backend && call .venv\Scripts\activate && set CORS_ALLOW_ORIGINS=%CORS_ALLOW_ORIGINS%&& uvicorn app.main:app --reload --host 127.0.0.1 --port %BACKEND_PORT%"

start "Vue Frontend" cmd /k "cd frontend && set VITE_API_BASE_URL=%API_BASE_URL%&& npm run dev -- --host 127.0.0.1 --port %FRONTEND_PORT%"

echo Серверы успешно запущены в новых окнах!
endlocal
goto :eof

:find_free_port
setlocal
set "RESULT_VAR=%~1"
set "START_PORT=%~2"
set "END_PORT=%~3"

for /L %%P in (%START_PORT%,1,%END_PORT%) do (
  findstr /R /C:":%%P .*LISTENING" "%PORT_CACHE%" >nul
  if errorlevel 1 (
    endlocal & set "%RESULT_VAR%=%%P"
    exit /b 0
  )
)

endlocal & exit /b 1
