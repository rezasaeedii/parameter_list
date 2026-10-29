@echo off
REM ===========================================================================
REM  Sets the version number of ParamGen - for whoever maintains the tool.
REM
REM  Double-click this file and type the new version as three pairs of
REM  digits separated by dots, like 01.01.85.  Or give it straight away:
REM      set_version.bat 01.01.85
REM
REM  The version lives in one line, src\pl_codegen\__init__.py, and everything
REM  that shows it reads it from there: the run.bat menu, "run.bat generate
REM  --version", the header of every generated file and the generatorVersion
REM  of every list the editor saves.  That line is all this changes; the
REM  manuals are updated by hand.
REM ===========================================================================
setlocal
cd /d "%~dp0"

REM "python is not recognised" in a window that then closes is no help to
REM anybody, so the Python is found the way run.bat finds it - the first one
REM that really starts - and when there is none it says so in words and waits.
call "%~dp0find_python.bat"
if not defined PYTHON (
    pause
    exit /b 9
)

echo.
"%PYTHON%" set_version.py %*
set EXITCODE=%ERRORLEVEL%

REM A double-click opens a window that would close on the result, so it waits;
REM "set_version.bat 01.01.85" typed in a console does not need to.
if "%~1"=="" goto :wait
if not "%EXITCODE%"=="0" goto :wait
exit /b %EXITCODE%

:wait
echo.
pause
exit /b %EXITCODE%
