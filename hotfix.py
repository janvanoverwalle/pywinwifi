import hashlib
import os.path
import shutil
import subprocess
import sys


def get_site_packages_path():
    output = subprocess.check_output(['where', 'python'], universal_newlines=True)
    python_location = output.splitlines()[0]
    python_directory = os.path.dirname(python_location)

    if os.path.basename(python_directory) == 'Scripts':
        python_directory = os.path.dirname(python_directory)

    path = os.path.join(python_directory, 'Lib', 'site-packages')
    if not os.path.exists(path):
        print(f'No such file or directory: "{path}"', file=sys.stderr)
        sys.exit(1)
    # print('Python environment located')

    return path


def get_package_file_path(package_name, package_file, site_packages_path=None):
    if not site_packages_path:
        site_packages_path = get_site_packages_path()

    path = os.path.join(site_packages_path, package_name)
    if not os.path.exists(path):
        print(f'No such package: "{os.path.basename(path)}". Make sure it is installed.',
              file=sys.stderr)
        sys.exit(1)
    # print('Package located')

    path = os.path.join(path, package_file)
    if not os.path.exists(path):
        print(f'No such file: "{os.path.basename(path)}" in "{os.path.dirname(path)}"',
              file=sys.stderr)
        sys.exit(1)
    # print('File located')

    return path


def calculate_md5(file_path):
    return hashlib.md5(open(file_path, 'rb').read()).hexdigest()


def apply_hotfix(package_name, package_file, site_packages_path=None):
    if not site_packages_path:
        site_packages_path = get_package_file_path(package_name, package_file)

    package_file_path = os.path.join(site_packages_path, package_name, package_file)
    current_directory = os.path.dirname(os.path.abspath(__file__))
    hotfix_file_path = os.path.join(current_directory, 'hotfixes', package_name, package_file)

    if calculate_md5(package_file_path) == calculate_md5(hotfix_file_path):
        print(f'Hotfix for package "{package_name}" has already been applied')
        return

    # print(f'Package "{package_name}" needs to be fixed')
    shutil.copyfile(hotfix_file_path, package_file_path)

    if calculate_md5(package_file_path) == calculate_md5(hotfix_file_path):
        print(f'Hotfix for package "{package_name}" has been successfully applied')


def main():
    site_packages_path = get_site_packages_path()

    apply_hotfix('win32wifi', 'Win32Wifi.py', site_packages_path)
    apply_hotfix('winwifi', 'main.py', site_packages_path)


if __name__ == '__main__':
    main()
