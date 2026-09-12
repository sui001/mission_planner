@echo off
REM ---------------------------------------------------------------------------
REM  Start the NTRIP proxy, wait for it, then launch Mission Planner.
REM
REM  Mission Planner cannot do TLS, so it cannot reach Geoscience Australia's
REM  caster directly. The proxy has to be up BEFORE Mission Planner tries to
REM  connect, otherwise the NTRIP box fails and has to be reconnected by hand.
REM
REM  Closing Mission Planner shuts the proxy down too, so nothing is left
REM  holding port 2101 and the next run starts clean.
REM
REM  Credentials are NOT in this file. They live in the JSON named below, which
REM  sits outside every git repo on purpose.
REM ---------------------------------------------------------------------------

setlocal

set "PROXY_DIR=%~dp0"
set "PYTHON=C:\Users\u4419394\AppData\Local\Programs\Python\Python312\python.exe"
set "MP=C:\Program Files (x86)\Mission Planner\MissionPlanner.exe"
set "CONFIG=%USERPROFILE%\.ntrip_grover.json"
set "TITLE=Grover NTRIP proxy"

if not exist "%CONFIG%" (
    echo.
    echo   No NTRIP config at %CONFIG%
    echo   Expected JSON with: server, port, mountpoint, user, password, lat, lon
    echo.
    pause
    exit /b 1
)

REM Kill a proxy left over from a previous run, so port 2101 is free. Killing
REM by port rather than window title: the process is python.exe and title
REM matching does not reliably find it, which leaves the port held.
"%PYTHON%" "%PROXY_DIR%stop_ntrip.py" >nul 2>&1

echo Starting NTRIP proxy...
start "%TITLE%" /min "%PYTHON%" -u "%PROXY_DIR%run_ntrip.py" "%CONFIG%"

REM Wait for it to actually bind rather than guessing at a sleep. Give up after
REM about 15 seconds and start Mission Planner anyway, so a caster problem does
REM not stop you flying without RTK.
echo Waiting for port 2101...
set /a TRIES=0
:waitloop
netstat -an | find ":2101" | find "LISTENING" >nul 2>&1
if not errorlevel 1 goto ready
set /a TRIES+=1
if %TRIES% GEQ 15 (
    echo   Proxy did not come up. Starting Mission Planner without RTK.
    echo   Check the minimised "%TITLE%" window for why.
    goto launch
)
REM ping rather than timeout: timeout fails outright with "Input redirection
REM is not supported" whenever stdin is not a console, which happens when this
REM is launched from a shortcut, a scheduler or another script.
ping -n 2 127.0.0.1 >nul
goto waitloop

:ready
echo   Proxy listening on http://localhost:2101
echo.

:launch
echo Starting Mission Planner...
echo Point the NTRIP box at:  http://localhost:2101/GNGN00AUS0
echo.
start /wait "" "%MP%"

echo Mission Planner closed. Stopping the proxy.
"%PYTHON%" "%PROXY_DIR%stop_ntrip.py"

endlocal
