
# pywinwifi
A Wi-Fi utility tool for Windows.

## Environment setup
Use `pip install -r requirements.txt` to install the required packages.

## Execution
Run `python pywinwifi.py ?` in a terminal to get started.

## Overview
The `help` or `?` argument displays a summary of all the available commands and their parameters and immediately exits.

### Functionality
- `poll`/`status`: Shows information about the currently connected Access point or AP.
- `scan`: Scan for available APs and display their properties. When provided with an optional SSID parameter, only the information pertaining to that SSID will be displayed.
- `connect`: Connect to an AP using its SSID and (optional) password. Supports an additional `remember` flag to save the credentials.
- `disconnect`: Disconnect from the currently connected AP, if any.
- `history`: Displays an overview of all the previously connected APs. When provided with an optional SSID parameter, only the information pertaining to that SSID will be displayed.
- `forget`: Deletes all stored information about a saved AP. When provided with optional SSID parameters, only the information pertaining to those SSIDs will be deleted.

### Modifiers
These arguments don't do anything by themselves and have to be combined with any of the functional argument.

- `repeat`: Repeats the corresponding argument by the provided amount.
- `interval`/`timeout`: Introduces a timeout after the corresponding argument has been performed. Usually used in combination with the `repeat` argument. _Note_: When no repeat amount is provided or after the last repeat iteration, the timeout will be ignored.
- `verbosity`: Increase the output verbosity. There are 3 levels of verbosity, each of them only adding additional output with regards the previous level.

## Logging
To enable file logging make sure that a folder named `logs` exists in the current working directory. When that directory exists, log files will be created on a per day basis (current date as filename) with separators between individual commands.

Individual commands are prefixed with a `CMD` tag. Following these is usually one (or more) command descriptions. These are in turn followed by the command output in JSON format, prefixed by a `JSON`tag.

_Note_: The `verbosity` argument also effects the logging output.