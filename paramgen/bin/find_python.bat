@echo off
REM ===========================================================================
REM  Finds the Python the tool runs on.  run.bat and set_version.bat do
REM      call "<this folder>\find_python.bat"
REM  and get PYTHON: the full path of a python.exe that really starts and is
REM  3.11 or newer.  With none, PYTHON stays empty and this says why.
REM
REM  The first "python" on the PATH is not always it.  The Python install
REM  manager puts a "python" shortcut into WindowsApps, which comes first on
REM  the PATH, and when that shortcut is broken it cannot even start ("The
REM  system cannot execute the specified program") - while a python.exe that
REM  works sits a few folders further on.  "Python was not found on this
REM  machine" was then all anybody was told, on a machine that had Python.
REM  So every Python is tried, in this order, and the first good one is used:
REM      1. every python.exe on the PATH (only .exe: a python.bat shim run from
REM         here would never come back to this file)
REM      2. the Python 3 the py launcher knows
REM      3. the folders Python installs itself into
REM
REM  No setlocal here: PYTHON has to reach the file that called this one.
REM ===========================================================================
set "PYTHON="
set "PYTHON_TOO_OLD="

for /f "delims=" %%p in ('where python.exe 2^>nul') do call :try "%%~p"
if defined PYTHON goto :eof

for /f "delims=" %%p in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do call :try "%%~p"
if defined PYTHON goto :eof

call :try "%LOCALAPPDATA%\Python\bin\python.exe"
for /d %%d in ("%LOCALAPPDATA%\Python\pythoncore-3*" "%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do call :try "%%~d\python.exe"
if defined PYTHON goto :eof

echo.
if defined PYTHON_TOO_OLD (
    echo     Python 3.11 or newer was not found on this machine.
    echo     The Python found is too old: %PYTHON_TOO_OLD%
) else (
    echo     Python was not found on this machine.
)
echo.
echo     Install Python 3.11 or newer from python.org and tick
echo     "Add python.exe to PATH" in the installer, then run this again.
echo.
goto :eof


REM -- one candidate: used when it starts and is new enough ------------------
:try
if defined PYTHON goto :eof
if not exist "%~1" goto :eof
"%~1" -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=%~1"
    goto :eof
)
REM It did not start, or it is too old.  Only one that starts says a version,
REM so a broken shortcut is passed over in silence.  "call" in front keeps cmd
REM from taking the quotes off a path with spaces in it.
for /f "delims=" %%v in ('call "%~1" --version 2^>nul') do set "PYTHON_TOO_OLD=%%v (%~1)"
goto :eof
