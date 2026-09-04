@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 run_vcu_tuner.py %*
  goto done
)
where python >nul 2>nul
if not errorlevel 1 (
  python run_vcu_tuner.py %*
  goto done
)
set "LOCAL_PY="
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%~fD\python.exe" set "LOCAL_PY=%%~fD\python.exe"
if defined LOCAL_PY (
  "%LOCAL_PY%" run_vcu_tuner.py %*
  goto done
)
echo Python 3 not found. Install Python 3 or run run_vcu_tuner.py with an existing interpreter.
:done
if errorlevel 1 pause
