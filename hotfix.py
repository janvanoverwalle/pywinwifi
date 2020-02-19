import os.path
import re
import subprocess
import sys


def main():
    output = subprocess.check_output(['where', 'python'], universal_newlines=True)
    python_location = output.splitlines()[0]
    python_directory = os.path.dirname(python_location)
    win32wifi_location = os.path.join(python_directory, 'Lib', 'site-packages', 'win32wifi', 'Win32Wifi.py')

    if not os.path.exists(win32wifi_location):
        print(f'No such file or directory: "{win32wifi_location}"', file=sys.stderr)
        sys.exit(1)

    contents = None
    with open(win32wifi_location) as in_file:
        contents = in_file.readlines()

    if not contents:
        print(f'No such file or empty file: "{win32wifi_location}"', file=sys.stderr)
        sys.exit(1)

    hotfixes_applied = 0
    hotfixes_already_applied = 0
    class_found = False
    method_found = False
    center_freq_added = False
    init_fixed = False
    append_fixed = False
    center_freq_line = 'self.ch_center_frequency = bss_entry.ChCenterFrequency'
    new_contents = contents[:]
    for index, line in enumerate(contents):
        stripped_line = line.strip()
        if stripped_line.startswith('class WirelessNetworkBss'):
            class_found = True
            continue
        if not class_found:
            continue
        if not center_freq_added:
            if stripped_line == center_freq_line:
                center_freq_added = True
                hotfixes_already_applied += 1
                continue
            if stripped_line.startswith('self.__process_information_elements'):
                i = line.find('self')
                new_contents.insert(index, f'{line[:i]}{center_freq_line}\n')
                center_freq_added = True
                hotfixes_applied += 1
                continue
        if stripped_line.startswith('def __process_information_elements'):
            method_found = True
            continue
        if not method_found:
            continue
        if stripped_line.startswith('self.raw_information_elements'):
            if not init_fixed:
                if stripped_line.endswith('[]'):
                    init_fixed = True
                    hotfixes_already_applied += 1
                    continue
                if stripped_line.endswith('""'):
                    new_contents[index+1] = new_contents[index+1].replace('""', '[]')
                    init_fixed = True
                    hotfixes_applied += 1
                    continue
            if not append_fixed:
                if stripped_line.endswith('.append(byte)'):
                    append_fixed = True
                    hotfixes_already_applied += 1
                    continue
                if stripped_line.endswith(' += str(byte)'):
                    new_contents[index+1] = new_contents[index+1].replace(' += str(byte)', '.append(byte)')
                    append_fixed = True
                    hotfixes_applied += 1
                    continue
        if hotfixes_applied + hotfixes_already_applied == 3:
            break
    else:
        print('Not all hotfixes have been applied', file=sys.stderr)
        sys.exit(1)

    if hotfixes_already_applied == 3:
        print('Hotfixes have already been succesfully applied')
        sys.exit(0)

    with open(win32wifi_location, 'w') as out_file:
        out_file.write(''.join(new_contents))

    print(f'Hotfixes ({hotfixes_applied}) have been succesfully applied')


if __name__ == '__main__':
    main()