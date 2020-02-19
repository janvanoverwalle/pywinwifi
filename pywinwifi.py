import argparse
import json
import os
import queue
import sys
import threading
import time

from logger import Logger
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

    def network_json(self):
        split_lines = [l.split(':', 1) for l in self.network_str().splitlines()]
        return {s[0].strip():s[1].strip() for s in split_lines}

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

    def bsss_json(self):
        l = []
        for bss in self.bsss:
            d = {
                'MAC': bss.bssid,
                'Band': f'{bss.band} GHz',
                'Signal': f'{bss.rssi} dBm'
            }
            if bss.channels and bss.channels[0]:
                delim = ''
                if len(bss.channels) > 1:
                    delim = '+' if bss.channels[0] < bss.channels[1] else '-'
                channels = delim.join(map(str, bss.channels))
                d['Channel'] = channels
            l.append(d)
        return {'BSSID': l}


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

    return res


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
    Logger.info(f'Connecting to SSID: {ssid}')
    try:
        WinWiFi.connect(ssid=ssid, passwd=password, remember=remember)
        ret = True
    except:
        ret = False
    Logger.info(f'JSON:{_to_json({"result": ret})}')
    return ret


def disconnect_ap():
    Logger.info('Disconnecting')
    try:
        WinWiFi.disconnect()
        ret = True
    except:
        ret = False
    Logger.info(f'JSON:{_to_json({"result": ret})}')
    return ret


def get_ap_history(callback=lambda x: None):
    try:
        return WinWiFi.get_profiles(callback=callback)
    except:
        return []


def forget_aps(*ssids):
    ssid_str = ', '.join(ssids) if ssids else ''
    ssid_str = f' ({ssid_str})' if ssid_str else ssid_str
    Logger.info(f'Forgetting APs{ssid_str}')
    try:
        WinWiFi.forget(*ssids)
        ret = True
    except:
        ret = False
    Logger.info(f'JSON:{_to_json({"result": ret})}')
    return ret


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
                error_msg = f'No matching network(s) found for SSID "{bss.ssid}"'
                if d_ssid:
                    error_msg += f' ("{d_ssid}")'
                Logger.error(error_msg)
                print(error_msg, file=sys.stderr)
                continue

            for network in networks:
                network.add_bss(bss)

    if ssid:
        if not isinstance(ssid, bytes):
            ssid = str(ssid).encode('utf-8')
        available_networks = [n for n in available_networks if n.ssid == ssid]
    for n in available_networks:
        try:
            n.ssid = n.ssid.decode('utf-8')
        except UnicodeDecodeError:
            pass
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


def _dict_to_str(d, sep=os.linesep):
    return sep.join(f'{k}:{v}' for k,v in d.items())


def _to_json(data):
    if isinstance(data, str):
        data = json.loads(data)
    return json.dumps(data)


def _get_parsed_ap_history():
    output = do_get_ap_history(1, log=False)
    profile_name = None
    next_is_profile = True
    ssid_profile_map = {}
    for line in output.splitlines():
        line = line.strip()
        if not line:
            next_is_profile = True
            continue
        if next_is_profile:
            profile_name = line[:-1]
            next_is_profile = False
            continue
        ssid_profile_map[line] = profile_name
    return ssid_profile_map


def do_interval(value, verbosity=0):
    if not value:
        if verbosity:
            Logger.info('No execution interval specified')
            print('No execution interval specified')
        return
    if verbosity:
        s = '' if value == 1 else 's'
        Logger.info(f'Delaying execution for {value} second{s}')
        print(f'Delaying execution for {value} second{s}')
    time.sleep(value)


def do_get_connected_ap(verbosity=0):
    Logger.info('Retrieving connected AP info')
    networks = get_connected_ap()
    for n in networks:
        if not verbosity:
            s = {'SSID': f'{n.ssid} ({n.state})'}
        else:
            s = {
                'Interface': f'{n.name}',
                'SSID': f'{n.ssid}',
                'State': f'{n.state}',
                'BSSID': f'{n.bssid}'
            }
        Logger.info(f'JSON:{_to_json(s)}')
        print(_dict_to_str(s))


def do_scan_networks(ssid, verbosity=0):
    Logger.info('Scanning for networks')
    networks = scan_networks(ssid)
    history = _get_parsed_ap_history() if verbosity == 0 else {}

    json_data = []
    for n in networks:
        log_msg = []
        if verbosity == 0:
            if n.profile_name and n.ssid in history:
                profile = f' ({history[n.ssid]})'
            else:
                profile = ''
            json_data.append(f'{n.ssid}{profile}')
            log_msg.append(f'{n.ssid}{profile}')
        log_data = {}
        if verbosity >= 1:
            log_data.update(n.network_json())
            log_msg.append(n.network_str())
        if verbosity >= 2:
            log_data.update(n.bsss_json())
            log_msg.append('\n'.join(l for l in n.bsss_str().splitlines() if l.strip()))
        if verbosity > 0:
            log_msg.append('')
        if log_data:
            json_data.append(log_data)
        log_msg = '\n'.join(log_msg)
        print(log_msg)
    Logger.info(f'JSON:{_to_json(json_data)}')


def do_get_ap_history(verbosity=0, **kwargs):
    do_log = kwargs.get('log', True)
    if do_log:
        Logger.info('Retrieving AP history')
    if not verbosity:
        hist = get_ap_history()
        if do_log:
            Logger.info(f'JSON:{_to_json(hist)}')
        return os.linesep.join(hist)
    output = []
    stdout = get_ap_history(callback=lambda x: output.append(x))
    if not output:
        return stdout
    new_output = []
    json_data = {}
    prev_line = ''
    prev_key = None
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
            prev_key = prev_line.strip()
            new_output.append(f'{prev_key}:')
            json_data[prev_key] = []
            do_append = True
        elif do_append:
            idx = line.find(':')
            if idx + 1:
                line = line[idx+1:]
            new_output.append(f'\t{line.strip()}')
            json_data[prev_key].append(line.strip())
        prev_line = line
    if do_log:
        Logger.info(f'JSON:{_to_json(json_data)}')
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

    Logger.info(f'CMD:{os.path.basename(__file__)} {" ".join(sys.argv[1:])}')

    try:
        args = parser.parse_args()
    except SystemExit:
        Logger.error('Invalid or incomplete argument')
        Logger.info('=' * 64)
        raise
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
        if args.verbosity:
            width = len(str(args.repeat))
            it_str = f'Executing iteration {i+1:>{width}}/{args.repeat}'
            Logger.info(it_str)
            print(it_str)
        output = exec_func()
        if output is not None:
            # Logger.info(output)
            if isinstance(output, bool):
                print('Success' if output else 'Error')
            else:
                print(output)
        if i < args.repeat-1:
            do_interval(args.interval, args.verbosity)
            print('-' * 32)
        Logger.info('=' * 64)


if __name__ == '__main__':
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y-%m-%d')
    Logger._configure_logger(filename=f'{timestamp}.log', append=True)
    main()
