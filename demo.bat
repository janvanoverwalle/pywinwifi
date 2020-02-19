@set CMD=python pywinwifi.py
@set SSID=<ssid>
@set PASSWD=<passwd>

@set /a iterations=1
@if not [%1] == [] (
  @set /a iterations=%1
)

@if exist logs ( rd /s /q logs )
@mkdir logs

@for /l %%x in (1, 1, %iterations%) do (
  @cls
  @echo Iteration %%x of %iterations%

  ::%CMD% --help
  ::@call :err_or_sleep
  %CMD% --scan
  @call :err_or_sleep
  %CMD% --scan %SSID%
  @call :err_or_sleep
  %CMD% --history
  @call :err_or_sleep
  %CMD% --history -v 1
  @call :err_or_sleep
  %CMD% --forget %SSID%
  @call :err_or_sleep
  %CMD% --history -v 1
  @call :err_or_sleep
  %CMD% --scan %SSID%
  @call :err_or_sleep
  %CMD% --scan %SSID% -v 1
  @call :err_or_sleep
  %CMD% --scan %SSID% -v 2
  @call :err_or_sleep
  %CMD% --status
  @call :err_or_sleep
  %CMD% --status -v 1
  @call :err_or_sleep
  %CMD% --connect %SSID% %PASSWD%
  @call :err_or_sleep
  %CMD% --status
  @call :err_or_sleep
  %CMD% --history
  @call :err_or_sleep
  %CMD% --disconnect
  @call :err_or_sleep
  %CMD% --status --repeat 3 --interval 3
  @call :err_or_sleep
)
@exit /b %ERRORLEVEL%

:err_or_sleep
@if errorlevel 1 (
   @exit /b %ERRORLEVEL%
)
@set /a t=5
@if not [%~1] == [] (
    @set /a t=%~1
)
@call :sleep %t%
@exit /b 0

:sleep
@set /a n=%~1+1
@ping 127.0.0.1 -n %n% > nul
@cls
@exit /b 0
