#! /usr/bin/env python3

import time
import os
import argparse
from serial import Serial, SerialException

from waggle.protocol.v5.decoder import decode_frame, convert, check_crc, create_crc

device = os.environ.get('CORESENSE_DEVICE', '/dev/waggle_coresense')

class DeviceHandler(object):
    def __init__(self, device):
        self.serial = Serial(device, baudrate=115200, timeout=180)

        self.START_BYTE = 0xAA
        self.END_BYTE = 0x55
        self.HEADER_SIZE = 3
        self.FOOTER_SIZE = 2
        self.SQN = 0

    def close(self):
        self.serial.close()

    def read_response(self):
        data = bytearray()
        packets = bytearray()
        while True:
            if self.serial.inWaiting() > 0 or len(data) > 0:
                data.extend(self.serial.read(self.serial.inWaiting()))
                # data.extend(self.serial.readline())

                # print(data)

                while True:
                    try:
                        del data[:data.index(self.START_BYTE)]
                    except ValueError:
                        del data[:]
                    
                    if len(data) >= self.HEADER_SIZE:
                        packet_length = data[2]
                        if len(data) >= self.HEADER_SIZE + packet_length + self.FOOTER_SIZE:
                            packet = data[:self.HEADER_SIZE + packet_length + self.FOOTER_SIZE]
                            crc = packet[-2]
                            if not check_crc(crc, packet[self.HEADER_SIZE:-2]):
                                return None
                            sequence = data[3]
                            packets.extend(packet)
                            del data[:len(packet)]
                            if (sequence & 0x80) == 0x80:
                                return packets
                    else:
                        break

            else:
                time.sleep(0.1)


    def request_data(self, sensors):
        # Packaging
        buffer = bytearray()
        buffer.append(0xAA) # preamble
        buffer.append(0x02) # data type ( request )
        buffer.append(len(buffer))
        third_byte = 0x80 | self.SQN
        if self.SQN < 0x7F:
            self.SQN += 1
        else:
            self.SQN = 0
        buffer.append(third_byte) # sequence ( 0 )
        data = bytearray()
        for i in range(0,len(sensors), 2):
            data.append(sensors[i]) # call function type
            data.append(0x01) # ack --> 0 1bit, 7-bit parameter length
            data.append(sensors[i + 1])
        buffer.extend(data)
        buffer[2] = len(data) + 1
        buffer.append(create_crc(buffer[3:])) # crc
        buffer.append(0x55) # postscript

        self.serial.write(bytes(buffer))
        return self.read_response()



class CoresensePlugin4(object):
    def __init__(self, input_handler, sensors, beehive=True, hrf=False):
        self.plugin_name = 'coresense'
        self.plugin_version = '4'
        self.sensors = sensors
        for sensor in self.sensors:
            s = self.sensors[sensor]
            s['last_updated'] = time.time()
            self.sensors[sensor] = s
        self.input_handler = input_handler
        self.beehive = beehive
        self.hrf = hrf

    def close(self):
        self.input_handler.close()

    def _get_requests(self):
        requests = []
        current_time = time.time()
        for sensor in self.sensors:
            s = self.sensors[sensor]
            if s['last_updated'] + s['interval'] < current_time:
                requests.append(s['function_call'])
                requests.append(s['sensor_id'])
                s['last_updated'] = current_time
                self.sensors[sensor] = s
        return requests

    def _print(self, packets, hrf=False):
        decoded = decode_frame(packets)
        # print(decoded)

        if isinstance(decoded, dict):
            for item in decoded:
                converted_value = convert(decoded[item], item)
                print(converted_value)
                # for entity in decoded[item]:
                #     entity_value = decoded[item][entity]
                #     converted_value = convert(entity_value, item, entity)
                #     print(converted_value)
        else:
            print('Error: Could not decode the packet %s' % (str(decoded),))


    def run(self):
        while True:
            # Blocking function
            requests = self._get_requests()
            if len(requests) > 0:
                # print(requests)
                message = self.input_handler.request_data(requests)

                if message is None:
                    print('Errors or invalid crc')
                else:
                    if self.beehive:
                        pass
                        # Send it to beehive
                    else:
                        self._print(message, hrf=args.hrf)
            else:
                time.sleep(0.5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--on-node', action='store_true', help='Run on node')
    parser.add_argument('--beehive', action='store_true', help='Report to Beehive')
    parser.add_argument('--hrf', action='store_true', help='Print in human readable form')
    args = parser.parse_args()

    sensor_table = {
        'MetMAC': { 'sensor_id': 0x00, 'function_call': 5, 'interval': 1 },  #o
        'TMP112': { 'sensor_id': 0x01, 'function_call': 5, 'interval': 1 },  #o
        'HTU21D': { 'sensor_id': 0x02, 'function_call': 5, 'interval': 1 },  #o
        'HIH4030': { 'sensor_id': 0x03, 'function_call': 5, 'interval':1 },  #o
        'BMP180': { 'sensor_id': 0x04, 'function_call': 5, 'interval': 1 },  #o
        'PR103J2': { 'sensor_id': 0x05, 'function_call': 5, 'interval': 1 },  #o
        'TSL250RDMS': { 'sensor_id': 0x06, 'function_call': 5, 'interval': 1 },  #o, light, return raw
        'MMA8452Q': { 'sensor_id': 0x07, 'function_call': 5, 'interval': 1 },  #o
        'SPV1840LR5H-B': { 'sensor_id': 0x08, 'function_call': 5, 'interval': 1 },  #o 63 readings
        'TSYS01': { 'sensor_id': 0x09, 'function_call': 5, 'interval': 1 },  #o

        'HMC5883L': { 'sensor_id': 0x0A, 'function_call': 5, 'interval': 1 },  #o
        'HIH6130': { 'sensor_id': 0x0B, 'function_call': 5, 'interval': 1 },  #o
        'APDS_9006_020': { 'sensor_id':0x0C, 'function_call': 5, 'interval': 1 },  #o, light, return raw
        'TSL260': { 'sensor_id': 0x0D, 'function_call': 5, 'interval': 1 },  #o, light, return raw
        'TSL250RDLS': { 'sensor_id': 0x0E, 'function_call': 5, 'interval': 1 },  #o, light, return raw
        'MLX75305': { 'sensor_id': 0x0F, 'function_call': 5, 'interval': 1 },  #o, light, return raw
        'ML8511': { 'sensor_id': 0x10, 'function_call': 5, 'interval': 1 },  #o, light, return raw
        'TMP421': { 'sensor_id': 0x13, 'function_call': 5, 'interval': 1 },  #o

        # 'ChemConfig': { 'sensor_id': 0x16, 'function_call': 5, 'interval': 1 },  #o
        # 'Chemsense': { 'sensor_id': 0x2A, 'function_call': 5, 'interval': 1 },  #o
        # 'Chemsense': { 'sensor_id': 0x2A, 'function_call': 5, 'interval': 1 },  #o
        # 'Chemsense': { 'sensor_id': 0x2A, 'function_call': 5, 'interval': 1 },  #o

        # 'AlphaON': { 'sensor_id': 0x2B, 'function_call': 5, 'interval': 5 },  #o
        # 'AlphaFirmware': { 'sensor_id': 0x30, 'function_call': 5, 'interval': 5 },  #o
        # 'AlphaSerial': { 'sensor_id': 0x29, 'function_call': 5, 'interval': 5 },  #o
        # 'AlphaHisto': { 'sensor_id': 0x28, 'function_call': 5, 'interval': 5 },  #o
        # 'AlphaConfig': { 'sensor_id': 0x31, 'function_call': 5, 'interval': 1 },
    }

    handler = None
    if args.on_node:
        handler = DeviceHandler(device)
    else:
        parser.print_help()
        exit(1)

    plugin = CoresensePlugin4(handler, sensors=sensor_table, beehive=args.beehive, hrf=args.hrf)
    try:
        plugin.run()
    except KeyboardInterrupt:
        pass
    finally:
        plugin.close()

