@cls
python pywinwifi.py --help
@call :sleep 5
python pywinwifi.py --scan
@call :sleep 5
python pywinwifi.py --scan Eurofins-Guest
@call :sleep 5
python pywinwifi.py --history
@call :sleep 5
python pywinwifi.py --history -v 1
@call :sleep 5
python pywinwifi.py --forget Eurofins-Guest
@call :sleep 5
python pywinwifi.py --history -v 1
@call :sleep 5
python pywinwifi.py --scan Eurofins-Guest
@call :sleep 5
python pywinwifi.py --scan Eurofins-Guest -v 1
@call :sleep 5
python pywinwifi.py --scan Eurofins-Guest -v 2
@call :sleep 5
python pywinwifi.py --status
@call :sleep 5
python pywinwifi.py --status -v 1
@call :sleep 5
python pywinwifi.py --connect Eurofins-Guest 4kIyEM:J-/
@call :sleep 5
python pywinwifi.py --status
@call :sleep 5
python pywinwifi.py --history
@call :sleep 5
python pywinwifi.py --disconnect
@call :sleep 5
python pywinwifi.py --status --repeat 3 --interval 3
@call :sleep 5
@exit /b %ERRORLEVEL%

:sleep
@set /a n=%~1+1
@ping 127.0.0.1 -n %n% > nul
@cls
@exit /b 0
