#!/usr/bin/env python

from gi.repository import GLib  # pyright: ignore[reportMissingImports]
import platform
import logging
# from logging.handlers import RotatingFileHandler
import sys
import os
from time import sleep, time
import configparser
import _thread
import threading
from dtupros import DtuProS


# import Victron Energy packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'ext', 'velib_python'))
from vedbus import VeDbusService

# Victron imports:
import dbus

CONFIG_FILE_NAME = "config.ini"
# LOG_FILE_NAME = "log.txt"

# get values from config.ini file
try:
    config_file = os.path.join((os.path.dirname(os.path.realpath(__file__))), CONFIG_FILE_NAME)
    if os.path.exists(config_file):
        config = configparser.ConfigParser()
        config.read(config_file)
    else:
        print(f'ERROR:The "{config_file}" is not found. The driver restarts in 60 seconds.')
        sleep(60)
        sys.exit()

except Exception:
    exception_type, exception_object, exception_traceback = sys.exc_info()
    file = exception_traceback.tb_frame.f_code.co_filename
    line = exception_traceback.tb_lineno
    print(f"Exception occurred: {repr(exception_object)} of type {exception_type} in {file} line #{line}")
    print("ERROR:The driver restarts in 60 seconds.")
    sleep(60)
    sys.exit()

log_levels = {'DEBUG': logging.DEBUG, 'INFO': logging.INFO, 'WARNING': logging.WARNING, 'ERROR': logging.ERROR,
              'CRITICAL': logging.CRITICAL}

logging.basicConfig(level=log_levels[config.get('DEFAULT', 'Logging', fallback='DEBUG')])

timeout = int(config.get('DEFAULT', 'Timeout', fallback=60))
data_lock = threading.Lock()
shared_data = []
last_changed = time()


def fetch_data():
    modbus_host = config['DEFAULT']['ModbusHost']
    modbus_port = config['DEFAULT']['ModbusPort']
    polling_interval = int(config.get('DEFAULT', 'PollingInterval', fallback=10))

    try:
        dtu = DtuProS(modbus_host, modbus_port)
        logging.info(f'Connection to DTU ({modbus_host}:{modbus_port}) successful')
    except Exception as e:
        logging.error(f"Exception while connecting: {e}")
        logging.error(f'Connection to DTU ({modbus_host}:{modbus_port}) failed!')
        print("ERROR:The driver restarts in 60 seconds.")
        sleep(60)
        sys.exit()

    number_of_ports = 99

    while True:
        try:
            start = time()
            dtu_data = dtu.read_inverter_data(number_of_ports)

            # if DTU data is read for the very first time, determine number of inverter ports
            if number_of_ports == 99:
                number_of_ports = len(dtu_data)

            with data_lock:
                global shared_data, last_changed
                shared_data = dtu_data
                last_changed = time()
                duration = last_changed - start
                logging.info(f"DTU: read {len(dtu_data)} data entries in {duration:.1f} sec")
        except Exception as e:
            logging.error(f"Exception while fetching data: {e}")

        if polling_interval > duration:
            sleep(polling_interval - duration)

class Inverter:
    def __init__(self, section):
        self.last_updated = 0
        self._sn = int(config[section]["SN"])
        self._model = f'{config.get(section, "Model", fallback="HOYMILES")}'
        self._phase = config[section]["Phase"]
        self._ac_position = int(config[section]["AcPosition"])
        self._unique_number = int(section[len("INVERTER"):])

        name = config.get(section, "Name", fallback="")
        if not name:
            name = f"{self._model}_{(self._sn % 1000):03d}"
        self._name = name

        self._service_name = f"com.victronenergy.pvinverter.dtupro_{self._unique_number}"
        self._device_instance = self._unique_number
        self._product_name = '3Gen DTU-Pro'
        self._custom_name = self._name
        self._connection = '3Gen DTU-Pro service'

        logging.info(f"Init inverter: sn={self._sn}, name={self._name}, model={self._model}, phase={self._phase}, "
                     f"ac_position={self._ac_position}, unique_number={self._unique_number}")

        paths_dbus = {
            '/Ac/Power': {'initial': 0, 'textformat': self._w},
            '/Ac/Energy/Forward': {'initial': None, 'textformat': self._kwh},
            '/Ac/MaxPower': {'initial': int(2000), 'textformat': self._w},  # TODO: enter some more meaningful here
            '/Ac/Position': {'initial': self._ac_position, 'textformat': self._n},
            '/Ac/StatusCode': {'initial': 0, 'textformat': self._n},
            '/UpdateIndex': {'initial': 0, 'textformat': self._n},
        }

        if self._phase == "L1":
            paths_dbus.update({
                '/Ac/L1/Power': {'initial': None, 'textformat': self._w},
                '/Ac/L1/Current': {'initial': None, 'textformat': self._a},
                '/Ac/L1/Voltage': {'initial': None, 'textformat': self._v},
                '/Ac/L1/Energy/Forward': {'initial': None, 'textformat': self._kwh},
            })

        if self._phase == "L2":
            paths_dbus.update({
                '/Ac/L2/Power': {'initial': None, 'textformat': self._w},
                '/Ac/L2/Current': {'initial': None, 'textformat': self._a},
                '/Ac/L2/Voltage': {'initial': None, 'textformat': self._v},
                '/Ac/L2/Energy/Forward': {'initial': None, 'textformat': self._kwh},
            })

        if self._phase == "L3":
            paths_dbus.update({
                '/Ac/L3/Power': {'initial': None, 'textformat': self._w},
                '/Ac/L3/Current': {'initial': None, 'textformat': self._a},
                '/Ac/L3/Voltage': {'initial': None, 'textformat': self._v},
                '/Ac/L3/Energy/Forward': {'initial': None, 'textformat': self._kwh},
            })

        if self._phase == "3P":
            paths_dbus.update({
                '/Ac/L1/Power': {'initial': None, 'textformat': self._w},
                '/Ac/L1/Current': {'initial': None, 'textformat': self._a},
                '/Ac/L1/Voltage': {'initial': None, 'textformat': self._v},
                '/Ac/L1/Energy/Forward': {'initial': None, 'textformat': self._kwh},
                '/Ac/L2/Power': {'initial': None, 'textformat': self._w},
                '/Ac/L2/Current': {'initial': None, 'textformat': self._a},
                '/Ac/L2/Voltage': {'initial': None, 'textformat': self._v},
                '/Ac/L2/Energy/Forward': {'initial': None, 'textformat': self._kwh},
                '/Ac/L3/Power': {'initial': None, 'textformat': self._w},
                '/Ac/L3/Current': {'initial': None, 'textformat': self._a},
                '/Ac/L3/Voltage': {'initial': None, 'textformat': self._v},
                '/Ac/L3/Energy/Forward': {'initial': None, 'textformat': self._kwh},
            })

        # Allow for multiple Instance per process in DBUS
        dbus_conn = (
            dbus.SessionBus()
            if "DBUS_SESSION_BUS_ADDRESS" in os.environ
            else dbus.SystemBus(private=True)
        )

        self._dbus_service = VeDbusService(f"{self._service_name}.http_{self._device_instance}", dbus_conn)
        self._paths = paths_dbus

        logging.debug("%s /DeviceInstance = %d" % (self._service_name, self._device_instance))

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbus_service.add_path('/Mgmt/ProcessName', __file__)
        self._dbus_service.add_path('/Mgmt/ProcessVersion',
                                    'Unknown version, and running on Python ' + platform.python_version())
        self._dbus_service.add_path('/Mgmt/Connection', self._connection)

        # Create the mandatory objects
        self._dbus_service.add_path('/DeviceInstance', self._device_instance)
        self._dbus_service.add_path('/ProductId', 0xFFFF)
        self._dbus_service.add_path('/ProductName', self._product_name)
        self._dbus_service.add_path('/CustomName', self._custom_name)
        self._dbus_service.add_path('/FirmwareVersion', '0.1.0 (20240317)')
        # self._dbusservice.add_path('/HardwareVersion', '')
        self._dbus_service.add_path('/Connected', 1)

        self._dbus_service.add_path('/Latency', None)
        self._dbus_service.add_path('/ErrorCode', 0)
        self._dbus_service.add_path('/Position', self._ac_position)  # only needed for pvinverter
        self._dbus_service.add_path('/StatusCode', 0)  # Dummy path so VRM detects us as a PV-inverter

        for path, settings in self._paths.items():
            self._dbus_service.add_path(
                path, settings['initial'], gettextcallback=settings['textformat'], writeable=True,
                onchangecallback=self._handle_changed_value
            )

        GLib.timeout_add(2000, self._update)  # pause before the next request

    # formatting
    @staticmethod
    def _kwh(p, v):
        return str("%.2f" % v) + "kWh"

    @staticmethod
    def _a(p, v):
        return str("%.1f" % v) + "A"

    @staticmethod
    def _w(p, v):
        return str("%i" % v) + "W"

    @staticmethod
    def _v(p, v):
        return str("%.2f" % v) + "V"

    @staticmethod
    def _hz(p, v):
        return str("%.4f" % v) + "Hz"

    @staticmethod
    def _n(p, v):
        return str("%i" % v)

    def _update(self):
        global last_changed, shared_data

        now = int(time())

        pv_grid_voltage = 0
        pv_power = 0
        pv_today_prod = 0
        pv_total_prod = 0

        with data_lock:
            last_changed_local = last_changed
            if shared_data:
                for d in shared_data:
                    if d["MicroInverterSN"] == self._sn:
                        pv_grid_voltage = d['GridVoltage']
                        pv_power += d['PVPower']
                        pv_today_prod += d['PVTodayProd']
                        pv_total_prod += d['PVTotalProd']

                pv_today_prod *= 1e-3  # DTU unit: Wh, DBUS unit: kWh
                pv_total_prod *= 1e-3  # DTU unit: Wh, DBUS unit: kWh

        if last_changed_local != self.last_updated:

            self._dbus_service['/Ac/Power'] = round(pv_power, 2)
            self._dbus_service['/Ac/Energy/Forward'] = round(pv_total_prod, 2)

            pv_grid_current = pv_power / pv_grid_voltage if pv_grid_voltage else 0

            if self._phase == 'L1' or self._phase == 'L2' or self._phase == 'L3':
                self._dbus_service[f'/Ac/{self._phase}/Voltage'] = round(pv_grid_voltage, 2)
                self._dbus_service[f'/Ac/{self._phase}/Current'] = round(pv_grid_current, 2)
                self._dbus_service[f'/Ac/{self._phase}/Power'] = round(pv_power, 2)
                self._dbus_service[f'/Ac/{self._phase}/Energy/Forward'] = round(pv_total_prod, 2)

            if self._phase == "3P":
                pv_power_div_by_three = pv_power / 3

                # Single Phase Voltage = (3-Phase Voltage) / (sqrt(3))
                # This formula assumes that the three-phase voltage is balanced and that
                # the phase angles are 120 degrees apart
                # sqrt(3) = 1.73205080757 <-- So we do not need to include Math Library
                single_phase_voltage = pv_grid_voltage / 1.73205080757
                #  single_phase_voltage = pv_grid_voltage

                real_current = pv_power_div_by_three / single_phase_voltage if single_phase_voltage else 0

                self._dbus_service["/Ac/L1/Voltage"] = single_phase_voltage
                self._dbus_service["/Ac/L1/Current"] = real_current
                self._dbus_service["/Ac/L1/Power"] = pv_power_div_by_three
                self._dbus_service["/Ac/L2/Voltage"] = single_phase_voltage
                self._dbus_service["/Ac/L2/Current"] = real_current
                self._dbus_service["/Ac/L2/Power"] = pv_power_div_by_three
                self._dbus_service["/Ac/L3/Voltage"] = single_phase_voltage
                self._dbus_service["/Ac/L3/Current"] = real_current
                self._dbus_service["/Ac/L3/Power"] = pv_power_div_by_three
                self._dbus_service["/Ac/Power"] = pv_power

                if pv_total_prod > 0:
                    self._dbus_service["/Ac/L1/Energy/Forward"] = pv_total_prod / 3
                    self._dbus_service["/Ac/L2/Energy/Forward"] = pv_total_prod / 3
                    self._dbus_service["/Ac/L3/Energy/Forward"] = pv_total_prod / 3
                    self._dbus_service["/Ac/Energy/Forward"] = pv_total_prod

            if pv_power:
                logging.debug(f"INVERTER{self._unique_number}: P={pv_power:.1f}W")

            self.last_updated = last_changed_local

        # quit driver if timeout is exceeded
        if timeout != 0 and (now - last_changed_local) > timeout:
            print(f"now={now}, last_changed={last_changed_local}, timeout={timeout}")
            sleep(5)
            logging.error(
                f'Driver stopped. Timeout of {timeout} seconds exceeded, since no new DTU message was received in '
                f'this time.')
            sys.exit()

        # increment UpdateIndex - to show that new data is available
        index = self._dbus_service['/UpdateIndex'] + 1  # increment index
        if index > 255:  # maximum value of the index
            index = 0  # overflow from 255 to 0
        self._dbus_service['/UpdateIndex'] = index
        return True

    @staticmethod
    def _handle_changed_value(self, path, value):
        logging.debug("someone else updated %s to %s" % (path, value))
        return True  # accept the change


def main():
    _thread.daemon = True  # allow the program to quit

    from dbus.mainloop.glib import DBusGMainLoop  # pyright: ignore[reportMissingImports]
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)

    logging.debug('Read config and setup inverters')
    for section in config.sections():
        if "INVERTER" in section:
            Inverter(section)

    # Start the thread which periodically reads from DTU
    fetch_thread = threading.Thread(target=fetch_data, daemon=True)
    fetch_thread.start()
    logging.debug('fetch_data thread started')

    logging.info('Connected to dbus and switching over to GLib.MainLoop() (= event based)')
    mainloop = GLib.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()
