@set CMD=python pywinwifi.py
@set SSID=Eurofins-Guest
@set PASSWD=4kIyEM:J-/

@cls
%CMD% --help
@call :sleep 5
%CMD% --scan
@call :sleep 5
%CMD% --scan %SSID%
@goto :eof
@call :sleep 5
%CMD% --history
@call :sleep 5
%CMD% --history -v 1
@call :sleep 5
%CMD% --forget %SSID%
@call :sleep 5
%CMD% --history -v 1
@call :sleep 5
%CMD% --scan %SSID%
@call :sleep 5
%CMD% --scan %SSID% -v 1
@call :sleep 5
%CMD% --scan %SSID% -v 2
@call :sleep 5
%CMD% --status
@call :sleep 5
%CMD% --status -v 1
@call :sleep 5
%CMD% --connect %SSID% %PASSWD%
@call :sleep 5
%CMD% --status
@call :sleep 5
%CMD% --history
@call :sleep 5
%CMD% --disconnect
@call :sleep 5
%CMD% --status --repeat 3 --interval 3
@call :sleep 5
@exit /b %ERRORLEVEL%

:sleep
@set /a n=%~1+1
@ping 127.0.0.1 -n %n% > nul
@cls
@exit /b 0
