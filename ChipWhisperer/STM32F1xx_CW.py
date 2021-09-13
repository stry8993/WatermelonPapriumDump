#!/opt/homebrew/bin/python3
#
# https://pcnews.ru/blogs/scityvanie_zasisennoj_prosivki_iz_fles_pamati_stm32f1xx_s_ispolzovaniem_chipwhisperer-953713.html#gsc.tab=0

import time
import sys
import logging
from chipwhisperer.common.utils import util
from chipwhisperer.hardware.naeusb.programmer_stm32fserial import supported_stm32f
from chipwhisperer.capture.api.programmers import Programmer

############## Library #################

# class which can normally using internal CW library for reading STM32 firmware by UART
class STM32Reader(Programmer):
    def __init__(self):
        super(STM32Reader, self).__init__()
        self.supported_chips = supported_stm32f

        self.slow_speed = False
        self.small_blocks = True
        self.stm = None

    def stm32prog(self):

        if self.stm is None:
            stm = self.scope.scopetype.dev.serialstm32f
        else:
            stm = self.stm

        stm.slow_speed = self.slow_speed
        stm.small_blocks = self.small_blocks

        return stm

    def stm32open(self):
        stm32f = self.stm32prog()
        stm32f.open_port()

    def stm32find(self):
        stm32f = self.stm32prog()
        stm32f.scope = self.scope
        sig, chip = stm32f.find()

    def stm32readMem(self, addr, lng):
        stm32f = self.stm32prog()
        stm32f.scope = self.scope
        #answer = stm32f.readMemory(addr, lng)
        answer = self.ReadMemory(addr, lng)
        return answer

    def stm32GetID(self):
        stm32f = self.stm32prog()
        stm32f.scope = self.scope
        answer = stm32f.cmdGetID()
        return answer

    # Needed for connection to STM after reload by reset_target(scope) method
    def FindSTM(self):
        #setup serial port (or CW-serial port?)
        stm32f = self.stm32prog()

        try:
            stm32f.initChip()
        except IOError:
            print("Failed to detect chip. Check following: ")
            print("   1. Connections and device power. ")
            print("   2. Device has valid clock (or remove clock entirely for internal osc).")
            print("   3. On Rev -02 CW308T-STM32Fx boards, BOOT0 is routed to PDIC.")
            raise

        boot_version = stm32f.cmdGet()
        chip_id = stm32f.cmdGetID()

        for t in supported_stm32f:
            if chip_id == t.signature:
#                print("Detected known STMF32: %s" % t.name)
                stm32f.setChip(t)
                return chip_id, t
#        print("Detected unknown STM32F ID: 0x%03x" % chip_id)
        return chip_id, None


def int2str_0xFF(int_number, number_of_bytes):
    return '{0:0{1}X}'.format(int_number,number_of_bytes_in_string)

def data_dividing_from_256_to_32_bytes (data_to_divide, mem_sector, mem_step=32):
    if mem_sector > 0xFFFF:
        mem_conversion = mem_sector >> 16
        mem_conversion = mem_sector - (mem_conversion << 16)
    data_out = ''
    for i in range(int(256/mem_step)):
        data_vector = data_to_divide[(i * mem_step):((i + 1) * mem_step)]
        mem_calc = mem_conversion + (i * mem_step)
        data_out += read_and_convert_data_hex_file(data_vector, mem_calc, mem_step) + '\n'
    return data_out

def read_and_convert_data_hex_file(data_to_convert, memory_address, mem_step):
    addr_string = memory_address -((memory_address >> 20) << 20)

    data_buffer = ''
    crcacc = 0
    for x in range(0, len(data_to_convert)):
        data_buffer += int2str_0xFF(data_to_convert[x], 2)
        crcacc += data_to_convert[x]

    crcacc += mem_step

    temp_addr_string = addr_string
    for i in range (4, -1, -2):
        crcacc += temp_addr_string >> i*4
        temp_addr_string -= ((temp_addr_string >> i*4) << i*4)

    crcacc_2nd_symbol = (crcacc >> 8) + 1
    crcacc = (crcacc_2nd_symbol << 8) - crcacc
    if crcacc == 0x100:
        crcacc = 0
    RECTYP = 0x00
    out_string = ':'+ Int_To_Hex_String(mem_step, 2)  +\
        Int_To_Hex_String((addr_string),4) +\
        Int_To_Hex_String(RECTYP, 2) +\
        data_buffer +\
        Int_To_Hex_String(crcacc, 2)
    return out_string

def send_to_file(info_to_output, File_name, directory):
    file = open(directory + File_name + '.hex', 'w')
    file.write(info_to_output)
    file.close()

def reset_target(scope):
    scope.io.nrst = 'low'
    time.sleep(0.05)
    scope.io.nrst = 'high'

from collections import namedtuple
Range = namedtuple('Range', ['min', 'max', 'step'])

############## Code omitted from article #################

prog = STM32Reader()  #api
prog.scope = scope
prog._logging = None
prog.stm32open()
prog.stm32find()

############## Code #################

# string of start HEX file
Start_of_File_Record = ':020000040800F2'
# Extended_Linera_Address_Record = ':020000040800F2'

# string of end HEX file
End_of_File_Record = ':00000001FF'

start_time = time.time()

length_of_sector = 256
if length_of_sector % 4 != 0:
    sys.exit('length_of_sector must be equal to 4')
#    sys.exit('data_with must be equal to 4')

output_to_file_buffer = ''
output_to_file_buffer += Start_of_File_Record + '\n'
#output_to_file_buffer += Extended_Linera_Address_Record + '\n'

mem_zero = 0x08000000
mem_64kBytes_counter = 0

mem_current = mem_start
while mem_current < mem_stop:
    # flush the garbage from the computer's target read buffer
    target.ser.flush()
    # run aux stuff that should run before the scope arms here
    reset_target(scope)
    # initialize STM32 after each reset
    prog.FindSTM()

    try:
        # reading of closed memory sector
        data = prog.stm32readMem(mem_current, length_of_sector)
    except Exception as message:
        message = str(message)
        if "Can't read port" in message:
#            print('Port silence')
            pass
        elif 'Unknown response. 0x11: 0x0' in message:
#            print('Crashed. Reload!')
            pass
        elif 'NACK 0x11' in message:
#            print('Firmware is closed!')
            pass
        else:
#            print('Unknown error:', message, scope.glitch.offset, scope.glitch.width, scope.glitch.ext_offset)
            pass

    else:
        data_to_out = data_dividing_from_256_to_32_bytes (data, mem_current)
        print(data_to_out)
        output_to_file_buffer += data_to_out
    mem_current += length_of_sector

output_to_file_buffer += End_of_File_Record + '\n'
send_to_file(output_to_file_buffer, File_name, directory)
print('success')
print('--- $s seconds ---" % (time.time() - start_time))

