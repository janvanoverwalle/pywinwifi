
# pywinwifi
A Wi-Fi utility tool for Windows.

## Environment setup
Use `pip install -r requirements.txt` to install the required packages.

### Dependencies
 - [win32wifi](https://github.com/kedos/win32wifi) by [kedos](https://github.com/kedos)
 - [winwifi.py](https://github.com/changyuheng/winwifi.py) by [changyuheng](https://github.com/changyuheng)

### Issues
At time of writing (Mar 11, 2020), there are a couple of issues with the following packages that need to be resolved:
 - `win32wifi`: See this [pull request](https://github.com/kedos/win32wifi/pull/8) for more information.
 - `winwifi`: See [issue #5](https://github.com/changyuheng/winwifi.py/issues/5) and [issue #8](https://github.com/changyuheng/winwifi.py/issues/8) for more information.

#### Hotfix
Either execute `hotfix.bat` or follow the steps below for each of the packagaes.

##### win32wifi
 1. Go to your Python environment's `site-packages` folder and locate the `win32wifi` folder. Open `Win32Wifi.py`  in your preferred text editor and look for the class `WirelessNetworkBss`.

 2. Add the following line to the class' `__init__` method, before the `__process_information_elements` methods.
   - `self.ch_center_frequency = bss_entry.ChCenterFrequency`

 3. Next go to the same class' `__process_information_elements` method and edit the following lines:
   - Change the `raw_information_elements` instantiation from empty string to empty list.\
   i.e. `self.raw_information_elements = []`
   - Change the `raw_information_elements` string concatenation of bytes to an append.\
   i.e. `self.raw_information_elements.append(byte)`

##### winwifi
 1. Go to your Python environment's `site-packages` folder and locate the `winwifi` folder. Open `main.py`  in your preferred text editor and look for the class `WinWiFi`.

 2. In the `gen_profile` method, after the `profile: str = cls.get_profile_template()` line, add the following code-block:
	```
	# (invalid_char, replace_by)
	invalid_chars = [
	    ('&', '&amp;'),  # Has to be checked first
	    ('"', '&quot;'),
	    ('\'', '&apos;'),
	    ('<', '&lt;'),
	    ('>', '&gt;')
	]
	for invalid_char in invalid_chars:
	    if invalid_char[0] in ssid:
	        ssid = ssid.replace(invalid_char[0], invalid_char[1])
	```
 3. In the same method add an `else` for the `if not passwd` statement with the following code-block:
	```
	profile = profile.replace('{passwd}', passwd)
	if auth.upper() == 'WPA2-PERSONAL':
	    auth = 'WPA2PSK'
	profile = profile.replace('{auth}', auth)
	if encrypt.upper() == 'CCMP':
	    encrypt = 'AES'
	profile = profile.replace('{encrypt}', encrypt)
	```
 4.  Next, in the same class' `connect` method, comment out the first line `if not passwd:` (and correct the indentation for the rest of the method's body).

## Execution
Run `python pywinwifi.py ?` in a terminal to get started.

## Overview
The `help` or `?` argument displays a summary of all the available commands and their parameters and immediately exits.

### Functionality
 - `poll`/`status`: Shows information about the currently connected Access point or AP.
 - `scan`: Scan for available APs and display their properties. When provided with an optional SSID parameter, only the information pertaining to that SSID will be displayed.
 - `connect`: Connect to an AP using its SSID and (optional) password. Supports an additional `remember` flag to automatically connect.
 - `disconnect`: Disconnect from the currently connected AP, if any.
 - `history`: Displays an overview of all the previously connected APs. When provided with an optional SSID parameter, only the information pertaining to that SSID will be displayed.
 - `forget`: Deletes all stored information about a saved AP. When provided with optional SSID parameters, only the information pertaining to those SSIDs will be deleted.

### Modifiers
These arguments don't do anything by themselves and have to be combined with any of the functional arguments.

 - `repeat`: Repeats the corresponding argument by the provided amount.
 - `interval`/`timeout`: Introduces a timeout after the corresponding argument has been performed. Usually used in combination with the `repeat` argument.\
 _Note_: When no repeat amount is provided or after the last repeat iteration, the timeout will be ignored.
 - `json`: Formats all (standard) output to the JSON format for easy parsing.
 - `verbosity`: Increase the output verbosity. There are 3 levels of verbosity, each of them only adding additional output with regards the previous level.

## Logging
To enable file logging make sure that a folder named `logs` exists in the current working directory. When that directory exists, log files will be created on a per day basis (current date as filename) with separators between individual commands.

Individual commands are prefixed with a `CMD` tag. Following these is usually one (or more) command descriptions. These are in turn followed by the command output in JSON format, prefixed by a `JSON`tag.

_Note_: The `verbosity` argument also affects the logging output.
