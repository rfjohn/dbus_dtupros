import logging

# pip3 install pymodbus
# from pymodbus.client import ModbusTcpClient  # recent pymodbus
from pymodbus.client.sync import ModbusTcpClient  # pymodbus <=v2.5.3
# from pymodbus import ModbusException


class DtuProS:
    def __init__(self, host, port=502):
        self._host = host
        self._port = port
        self._client = None
        self._dtu_serial = None

        self._client = ModbusTcpClient(host=self._host, port=self._port)
        self._client.connect()
        logging.debug(f"Connection to modbus client {self._host}:{self._port} established.")

    def __del__(self):
        if self._client:
            self._client.close()
            logging.debug(f"Connection to modbus client {self._host}:{self._port} closed.")

    @staticmethod
    def __unsigned2signed(unsigned_value):
        signed_value = unsigned_value if unsigned_value < (1 << 16 - 1) else unsigned_value - (1 << 16)
        return signed_value

    def read_dtu_serial(self):
        offset_base = 0x2000

        rr = self._client.read_holding_registers(offset_base, 6)
        if rr.isError():
            logging.error(f"Received Modbus library error({rr})")
            self._client.close()
            return None

        regs = rr.registers
        return (f'{regs[0]:X}' + f'{regs[1]:X}' + f'{regs[2]:X}' + f'{regs[3]:X}')[:-1]

    def read_inverter_data(self, num_ports=99):
        # maximum number_of_ports: 99
        offset_base = 0x1000
        offset_step = 0x28

        result = []

        for port_nr in range(num_ports):
            rr = self._client.read_holding_registers(offset_base + offset_step * port_nr, 20)
            if rr.isError():
                logging.error(f"Received Modbus library error({rr})")
                self._client.close()
                return None

            regs = rr.registers
            sn = int((f'{regs[0]:x}' + f'{regs[1]:x}' + f'{regs[2]:x}' + f'{regs[3]:x}')[1:-2])

            if not sn:
                return result

            single_port_result = {
                "MicroInverterSN": sn,
                "PortNumber": regs[3] & 0x00ff,
                "PVVoltage": regs[4] / 10,
                "PVCurrent": regs[5] / 100,
                "GridVoltage": regs[6] / 10,
                "GridFreq": regs[7] / 100,
                "PVPower": regs[8] / 10,
                "PVTodayProd": regs[9],
                "PVTotalProd": regs[10] * 65536 + regs[11],
                "Temp": self.__unsigned2signed(regs[12]) / 10,
                "OperatingStatus": regs[13],
                "AlarmCode": regs[14],
                "AlarmCount": regs[15],
                "LinkStatus": regs[16],
            }

            result.append(single_port_result)

        return result
