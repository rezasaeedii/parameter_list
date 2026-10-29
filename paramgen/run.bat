@echo off
REM ===========================================================================
REM  The parameter list code generator - everything it can do, in one place.
REM
REM  Double-click this file.  It asks what you want:
REM
REM      1  Editor          open a project and edit its parameter lists
REM      2  Generate code   write the C files of the project opened last
REM      3  Tests           run every self test of the tool
REM      4  Check this PC   is the Python on this machine complete enough?
REM
REM  This folder is the APP: copied once per machine, never written to while
REM  you work.  The lists and the generated code belong to a PROJECT, which is
REM  a folder somewhere else with a pl_project.json in it.
REM
REM  Straight to one of them, without the menu:
REM      run.bat editor      run.bat tests
REM      run.bat editor ..\projects\demo
REM      run.bat generate -c ..\projects\demo --check
REM
REM  Nothing is installed and nothing is downloaded: the tool uses only the
REM  Python standard library, because the machines it runs on are offline.
REM
REM  This is the only file you ever start here.  bin\ holds the entry points,
REM  src\ the code, templates\ what a new project is made of, docs\ the
REM  manuals, tests\ the tool's own tests and var\ the state it writes.
REM ===========================================================================
setlocal
cd /d "%~dp0"

REM Python itself is the one thing that has to be there already, and "python
REM is not recognised" in a window that then closes is no help to anybody.
REM Which Python: the first one on this machine that really starts and is new
REM enough - not simply the first "python" on the PATH, which can be a broken
REM shortcut with a working Python right behind it.  See bin\find_python.bat.
call "%~dp0bin\find_python.bat"
if not defined PYTHON (
    pause
    exit /b 9
)

"%PYTHON%" bin\run.py %*
set EXITCODE=%ERRORLEVEL%

REM The menu already says how each action ended and waits for Enter itself, so
REM the plain double-click needs no pause here.  The "run.bat tests" form does
REM - the window would close on the result - and so does any failure, which is
REM the one message that must never scroll past into a closing window.
if not "%~1"=="" goto :wait
if not "%EXITCODE%"=="0" goto :wait
exit /b %EXITCODE%

:wait
echo.
pause
exit /b %EXITCODE%
