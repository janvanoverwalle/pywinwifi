import argparse
import os
import queue
import sys
import threading
import time

from win32wifi.Win32Wifi import *
from winwifi import WinWiFi


class WlanNotificationThread(threading.Thread):
    def __init__(self, state, exit_event=None):
        super().__init__()
        self.notification_state = str(state)
        self.exit_event = exit_event
        self._thread_lock = threading.Lock()
        self._work_queue = queue.Queue(8)
        self._notification_object = None

        if not self.notification_state.startswith('wlan_notification_acm_'):
            self._notification_state = f'wlan_notification_acm_{self.notification_state}'
        else:
            self._notification_state = self.notification_state

    def run(self):
        self._register_callback()

        while True:
            if self.exit_event and self.exit_event.isSet():
                break
            self._lock()
            if self._work_queue.empty():
                self._unlock()
            else:
                obj = self._work_queue.get()
                self._unlock()
                if str(obj) == self._notification_state:
                    break
            time.sleep(.5)

        self._unregister_callback()

    def _lock(self):
        self._thread_lock.acquire()

    def _unlock(self):
        self._thread_lock.release()

    def _register_callback(self):
        if self._notification_object:
            print('Notification object already exists, unregistering it')
            self._unregister_callback()
        self._notification_object = registerNotification(self._notification_callback)

    def _unregister_callback(self):
        if not self._notification_object:
            return
        unregisterNotification(self._notification_object)

    def _notification_callback(self, obj):
        self._lock()
        self._work_queue.put(obj)
        self._unlock()


class ExtWirelessNetworkBss(WirelessNetworkBss):
    # NOTE: Manually modified 'WirelessNetworkBss.__process_information_elements'
    #       in Win32Wifi.py (site-packages)
    # See https://github.com/kedos/win32wifi/pull/8 for more info
    @classmethod
    def cast(cls, obj:WirelessNetworkBss):
        obj.__class__ = cls
        # NOTE: Manually modified 'WirelessNetworkBss.__init__'
        #       in Win32Wifi.py (site-packages)
        # See https://github.com/kedos/win32wifi/pull/8 for more info
        obj.band = '5' if str(obj.ch_center_frequency)[0] == '5' else '2.4'
        obj.channels = obj._get_channels_from_information_elements()
        return obj

    def __str__(self):
        s = 's' if len(self.channels) > 1 else ''
        channels = ', '.join(map(str, self.channels))
        return os.linesep.join((
            f'SSID: {self.ssid}',
            f'BSSID: {self.bssid}',
            f'Band: {self.band} GHz',
            f'Signal: {self.rssi} dBm',
            f'Channel{s}: {channels}'
        ))

    def _get_channels_from_information_elements(self):
        channel_1 = 0
        channel_2 = 0
        is_40_mhz = False
        supports_40_mhz = False

        for ie in self.information_elements:
            # Based on https://github.com/metageek-llc/ManagedWifi/blob/master/IEParser.cs
            # https://mrncciew.com/2014/10/19/cwap-ht-capabilities-ie/
            # https://mrncciew.com/2014/11/04/cwap-ht-operations-ie/
            if ie.element_id == 45:  # HT Capabilities
                INFO = 0
                supports_40_mhz = (ord(ie.body[INFO]) & 0x02) == 0x02
            elif ie.element_id == 61:  # HT Operations
                CHANNEL = 0
                SUBSET_1 = 1
                channel_1 = ord(ie.body[CHANNEL])
                if supports_40_mhz:
                    is_40_mhz = (ord(ie.body[SUBSET_1]) & 0x03) == 0x03 or \
                                (ord(ie.body[SUBSET_1]) & 0x01) == 0x01
                if is_40_mhz:
                    is_ch_2_lower = (ord(ie.body[SUBSET_1]) & 0x03) == 0x03
                    channel_2 = channel_1 + (-1 if is_ch_2_lower else 1) * 4
            elif ie.element_id == 191:
                # Ignore
                # print(f'Found VHT Capabilities for "{self.ssid}"', file=sys.stderr)
                pass
            elif ie.element_id == 192:
                # Ignore
                # print(f'Found VHT Operations for "{self.ssid}"', file=sys.stderr)
                pass
        return (channel_1, channel_2) if channel_2 else (channel_1,)


class ExtWirelessNetwork(WirelessNetwork):
    @classmethod
    def cast(cls, obj:WirelessNetwork):
        obj.__class__ = cls
        obj.bsss = []
        return obj

    def add_bss(self, bss):
        self.bsss.append(bss)

    def __str__(self):
        return os.linesep.join((self.network_str().strip(),
                                self.bsss_str().strip()))

    def network_str(self):
        return super().__str__().strip()

    def bsss_str(self):
        s = []
        for idx, bss in enumerate(self.bsss):
            s.append(f'BSSID {idx+1}')
            s.append(f'\tMAC: {bss.bssid}')
            s.append(f'\tBand: {bss.band} GHz')
            s.append(f'\tSignal: {bss.rssi} dBm')
            if not bss.channels or not bss.channels[0]:
                continue
            delim = ''
            if len(bss.channels) > 1:
                delim = '+' if bss.channels[0] < bss.channels[1] else '-'
            plural = 's' if len(bss.channels) > 1 else ''
            channels = delim.join(map(str, bss.channels))
            s.append(f'\tChannel{plural}: {channels}')
        return os.linesep.join(s)


def _wlan_get_interfaces(state=None):
    """
    :Args:
     - state:   (str) The current state of the interfaces to retrieve.
                Can be one of:
                    ad_hoc_network_formed, associating, authenticating,
                    connected, disconnected, disconnecting, discovering,
                    not_ready
                Default returns all, regardless of the current state.
    """
    interfaces = getWirelessInterfaces()
    if not state:
        return interfaces
    if not state.startswith('wlan_interface_state_'):
        state = f'wlan_interface_state_{state}'
    requested_interfaces = []
    for interface in interfaces:
        res = queryInterface(interface, 'current_connection')
        if res[1].get('isState') == state:
            requested_interfaces.append(interface)
    return requested_interfaces


def _wlan_scan_interface(interface, timeout=10):
    exit_event = threading.Event() if timeout else None
    notification_thread = WlanNotificationThread('scan_complete', exit_event)
    notification_thread.start()

    handle = WlanOpenHandle()
    res = WlanScan(handle, interface.guid)
    WlanCloseHandle(handle)

    if timeout:
        notification_thread.join(timeout)
        exit_event.set()
    notification_thread.join()


def get_connected_ap():
    try:
        return list(map(lambda i: i, WinWiFi.get_connected_interfaces()))
    except:
        return []


def scan_aps(callback=lambda x: None):
    # Not used at the moment
    try:
        return WinWiFi.scan(callback=callback)
    except:
        return []


def connect_ap(ssid, password='', remember=False):
    try:
        WinWiFi.connect(ssid=ssid, passwd=password, remember=remember)
    except:
        return False
    return True


def disconnect_ap():
    try:
        WinWiFi.disconnect()
    except:
        return False
    return True


def get_ap_history(callback=lambda x: None):
    try:
        return WinWiFi.get_profiles(callback=callback)
    except:
        return []


def forget_aps(*ssids):
    try:
        WinWiFi.forget(*ssids)
    except:
        return False
    return True


def scan_networks(ssid=None):
    # Loosely based on (and uses): https://github.com/kedos/win32wifi
    available_networks = []
    interfaces = getWirelessInterfaces()
    for interface in interfaces:
        # print(f'Interface: {interface}')

        _wlan_scan_interface(interface)  # Scan for wireless networks
        # print()

        networks = getWirelessAvailableNetworkList(interface)
        available_networks.extend([ExtWirelessNetwork.cast(n) for n in networks])
        # print(f'Networks found: {len(networks)}')

        bss_entries_list = getWirelessNetworkBssList(interface)
        # print(f'BSS entries found: {len(bss_entries_list)}')
        bsss = [ExtWirelessNetworkBss.cast(b) for b in bss_entries_list]

        for bss in bsss:
            if not bss.ssid:
                continue  # Ignore empty SSIDs

            networks = [n for n in available_networks if n.ssid == bss.ssid]
            if not networks:
                try:
                    d_ssid = bss.ssid.decode('utf-8')
                except UnicodeDecodeError:
                    d_ssid = ''
                error_msg = f'No matching network found for SSID "{bss.ssid}"'
                if d_ssid:
                    error_msg += f' ("{d_ssid}")'
                print(error_msg, file=sys.stderr)
                continue

            for network in networks:
                network.add_bss(bss)

    if ssid:
        if not isinstance(ssid, bytes):
            ssid = str(ssid).encode('utf-8')
        available_networks = [n for n in available_networks if n.ssid == ssid]
    return available_networks


""" CLI definitions """

class CustomHelpFormatter(argparse.HelpFormatter):
    def _format_args(self, action, default_metavar):
        get_metavar = self._metavar_formatter(action, default_metavar)
        if action.nargs == argparse.ONE_OR_MORE:
            metavar_len = len(get_metavar(1))
            if metavar_len > 1:
                opts = ('[%s] ' * max(0, metavar_len - 1)).strip()
                s = f'%s {opts}' if opts else '%s'
                return s % get_metavar(1)
        return super()._format_args(action, default_metavar)


class ConnectArgsAction(argparse.Action):
    def __call__(self, parser, args, values, option_string=None):
        if not 1 <= len(values) <= 3:
            msg = (
                f'argument "{self.dest}" requires an SSID parameter, '
                'an optional PASSWORD parameter '
                'and an optional REMEMBER parameter'
            )
            raise argparse.ArgumentTypeError(msg)
        setattr(args, self.dest, values)


def _str_to_bool(s):
    s = str(s).strip()
    if not s:
        return False
    return s.lower() not in ('false', 'f', '0', 'no', 'n')


def do_get_connected_ap(verbosity=0):
    networks = get_connected_ap()
    for n in networks:
        if not verbosity:
            s = [f'SSID: {n.ssid} ({n.state})']
        else:
            s = [
                f'Interface: {n.name}',
                f'SSID: {n.ssid}',
                f'State: {n.state}',
                f'BSSID: {n.bssid}'
            ]
        print(os.linesep.join(s))


def do_scan_networks(ssid, verbosity=0):
    networks = scan_networks(ssid)
    for n in networks:
        if verbosity == 0:
            print(n.ssid)
        if verbosity >= 1:
            print(n.network_str())
        if verbosity >= 2:
            print(n.bsss_str())
        if verbosity > 0:
            print()


def do_get_ap_history(verbosity=0):
    if not verbosity:
        return get_ap_history()
    output = []
    stdout = get_ap_history(callback=lambda x: output.append(x))
    if not output:
        return stdout
    new_output = []
    prev_line = None
    do_append = True
    for line in output[0].splitlines():
        if not line:
            if do_append:
                new_output.append('')
            do_append = False
        elif line == '-' * len(line):
            idx = prev_line.find('(')
            if idx + 1:
                prev_line = prev_line[:idx-1]
            new_output.append(f'{prev_line.strip()}:')
            do_append = True
        elif do_append:
            idx = line.find(':')
            if idx + 1:
                line = line[idx+1:]
            new_output.append(f'\t{line.strip()}')
        prev_line = line
    return os.linesep.join(new_output).strip()


def create_parser(prog_name=None):
    parser = argparse.ArgumentParser(prog=prog_name,
                                     formatter_class=CustomHelpFormatter)
    parser.add_argument('-p', '--poll', '--status',
                        dest='status',
                        action='store_true',
                        help='show currently connected AP')
    parser.add_argument('-s', '--scan',
                        nargs='?',
                        type=str,
                        const=True,
                        metavar='SSID',
                        help='scan for APs')
    parser.add_argument('-c', '--connect',
                        action=ConnectArgsAction,
                        nargs='+',
                        metavar=('SSID', 'PASSWORD', 'REMEMBER'),
                        help='connect to AP')
    parser.add_argument('-d', '--disconnect',
                        action='store_true',
                        help='disconnect from AP')
    parser.add_argument('-y', '--history',
                        nargs='?',
                        type=str,
                        const=True,
                        metavar='SSID',
                        help='shows AP history')
    parser.add_argument('-f', '--forget',
                        nargs='+',
                        type=str,
                        metavar='SSID',
                        help='forget AP details')
    parser.add_argument('-r', '--repeat',
                        type=int,
                        default=1,
                        metavar='AMOUNT',
                        help='repeat argument <AMOUNT> times')
    parser.add_argument('-i', '--interval', '-t', '--timeout',
                        dest='interval',
                        type=int,
                        default=0,
                        metavar='SECONDS',
                        help='repetition interval')
    parser.add_argument('-v', '--verbosity',
                        type=int,
                        default=0,
                        help='increase output verbosity [0-2]')
    return parser


def main():
    parser = create_parser()

    if len(sys.argv) == 1:
        parser.print_usage()
        sys.exit(1)
    if sys.argv[1] == '?':
        parser.print_help()
        sys.exit()

    args = parser.parse_args()
    # print(vars(args))

    args.verbosity = max(0, args.verbosity)  # Clamp the verbosity between [0,x]
    exec_func = None
    if args.status:
        exec_func = lambda: do_get_connected_ap(args.verbosity)
    elif args.scan:
        ssid = args.scan if isinstance(args.scan, str) else None
        exec_func = lambda: do_scan_networks(ssid, args.verbosity)
    elif args.connect:
        ssid = args.connect[0]
        password = args.connect[1] if len(args.connect) > 1 else ''
        remember = args.connect[2] if len(args.connect) > 2 else False
        exec_func = lambda: connect_ap(ssid,
                                       password=password,
                                       remember=_str_to_bool(remember))
    elif args.disconnect:
        exec_func = disconnect_ap
    elif args.history:
        exec_func = lambda: do_get_ap_history(args.verbosity)
    elif args.forget:
        if isinstance(args.forget, (list, tuple)):
            fargs = args.forget
        else:
            fargs = (args.forget,)
        exec_func = lambda: forget_aps(*fargs)

    if not exec_func:
        return

    for i in range(args.repeat):
        output = exec_func()
        if not output:
            output = tuple()
        elif not isinstance(output, (list, tuple)):
            output = (output,)
        for o in output:
            print(o)
        if args.interval and i < args.repeat-1:
            time.sleep(args.interval)


if __name__ == '__main__':
    main()
