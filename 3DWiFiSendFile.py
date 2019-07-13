#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Known to work with QIDI X-Pro and X-Max 3dprinters

# sources for M Commands:
#
# experimentation with 'echo "M4001" | nc -u 192.168.3.100 3000'
#   -and-
# observation of QIDI Print softare via tcpdump:  'sudo tcpdump -i en9 -nn -s0 -v host 192.168.3.100'
#   -and-
# https://reprap.org/wiki/G-code#M115:_Get_Firmware_Version_and_Capabilities
# https://www.craftbot.nl/2015/07/07/list-of-m-and-g-commands-as-used-by-the-craftbot/
# https://github.com/Photonsters/anycubic-photon-docs/blob/master/photon-blueprints/readme.md
# https://github.com/Photonsters/anycubic-photon-docs/blob/master/photon-blueprints/ChituClientWifiProtocol-translated.txt

import sys
import platform
import logging
import time
from socket import *
import struct
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import re

import subprocess
import os
from os import path

# TODO: should initialize with all data set - you know, encapsulation and all that...
class WiFiDevice():
    # TODO: put the codes in a separate file for ease of reading, etc
    # TODO: better documentation on what codes do
    CMD_PRINTING_STATUS = "M27" # reports on printing status
    CMD_STARTWRITE_SD = "M28 "  # start writing datagrams to SD
    CMD_ENDWRITE_SD = "M29 "    # stop writing datagrams to SD
    CMD_GETFILELIST = "M20 "    # SD card file list. "M20 'P/<subdirectory>'"  second part is optional, root otherwise
    CMD_DELETE_FILE_SD = "M30 "  # requires filename arguement
    CMD_CURRENT_POSITION = "M114"   #current position
    CMD_STATUS = "M115 "        # printer board manufacturer / firmware
    CMD_MSTATUS = "M119 "
    CMD_BED_INFO = "M4000 "
    CMD_PRINTER_INFO = "M4001 " # printer bed info
    CMD_FIRMWARE = "M4002 "
    CMD_OFF = "M4003 "
    CMD_PRINT_SD = "M6030 "

    PORT = 3000
    # TODO: find this in the windows qidi software install and refer to it
    # TODO: also add platform.system() check like below
    # TODO: and remove the .exe from git
    VC_COMPRESS = ".\VC_compress_gcode.exe"
    if platform.system() == 'Darwin':  # for MacOS.  wish python had proper ternary operators....
        VC_COMPRESS = "/Applications/QIDI-Print.app//Contents/MacOS/VC_compress_gcode_MAC"
    CONNECT_TIMEOUT = 5

    def __init__(self):
        self.ipaddr = ''
        self.name = 'undefined'
        self.BUFSIZE = 256 * 5
        self.RECVBUF = 256 * 5
        self.gcodeFile = 'data.gcode'
        self.fileName = 'data.gcode.tz'
        self.dirPath = ''
        self.sock = socket(AF_INET, SOCK_DGRAM)
        self.sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        self.sock.setblocking(0) # note: experimental, default is 1
        self.sock.settimeout(5)
        self._file_encode = 'utf-8'

    def __str__(self):
        s = ('Device addr:' + self.ipaddr + '==' + self.name)
        return s

    def encodeCmd(self,cmd):
        return cmd.encode(self._file_encode, 'ignore')

    def decodeCmd(self,cmd):
        return cmd.decode(self._file_encode,'ignore')

    # TODO: check to see if file already exists, and recover if it does
    def sendStartWriteSd(self):
        cmd = self.CMD_STARTWRITE_SD + self.fileName
        logger.info("Start write to SD: " + cmd)
        self.sock.sendto(self.encodeCmd(cmd), (self.ipaddr, self.PORT))
        message, address = self.sock.recvfrom(self.RECVBUF)
        message = message.decode('utf-8','replace')
        logger.info("Start write to SD result: " + message)
        return

    # TODO: check if file is correct bytes, etc on SD after transfer
    def sendEndWriteSd(self):
        cmd = self.CMD_ENDWRITE_SD + self.fileName
        logger.info("End write to SD: " + cmd)
        self.sock.sendto(self.encodeCmd(cmd), (self.ipaddr, self.PORT))
        message, address = self.sock.recvfrom(self.RECVBUF)
        message = message.decode('utf-8','replace')
        logger.info("End write to SD result: " + message)
        return

    def sendCmd(self, cmd):
        #cmd = self.CMD_GETFILELIST
        logger.info("sending: " + cmd)
        self.sock.sendto(self.encodeCmd(cmd), (self.ipaddr, self.PORT))
        message, address = self.sock.recvfrom(self.RECVBUF)
        message = message.decode('utf-8','replace')
        logger.info("Get list of files result: " + message)
        return

    def addCheckSum(self, data, seekPos):

        seekArray = struct.pack('>I', seekPos)

        check_sum = 0
        data += b"000000"
        dataArray = bytearray(data)

        datSize = len(dataArray) - 6

        if datSize <= 0:
            return

        dataArray[datSize] = seekArray[3]
        dataArray[datSize + 1] = seekArray[2]
        dataArray[datSize + 2] = seekArray[1]
        dataArray[datSize + 3] = seekArray[0]

        for i in range(0, datSize+4, 1):
            check_sum ^= dataArray[i]

        dataArray[datSize + 4] = check_sum
        dataArray[datSize + 5] = 0x83

        return dataArray

    def sendFileChunk(self, buff, seekPos):

        logger.info("File Position: " + str(seekPos))
        tmpArray = bytearray(buff)
        tmpSize = len(tmpArray)
        if tmpSize <= 0:
            return

        dataArray = self.addCheckSum(buff, seekPos)

        datSize = len(dataArray) - 6

        if datSize <= 0:
            logger.warning('Error computing checksum: Data size is 0')
            return

        self.sock.sendto(dataArray, (self.ipaddr, self.PORT))

        message, address = self.sock.recvfrom(self.RECVBUF)
        message = message.decode('utf-8','replace')
        logger.info("Sending File Chunk result: " +  message)

        return


    def sendFile(self):

        with open(self.fileName, 'rb', buffering=1) as fp:
            while True:
                seekPos = fp.tell()
                chunk = fp.read(self.BUFSIZE)
                if not chunk:
                    break

                self.sendFileChunk(chunk, seekPos)

        logger.info("End write SendFile ")
        fp.close()

        return


    def dataCompressThread(self):
        logger.info("Compressing Gcode File")
        self.datamask = '[0-9]{1,12}\.[0-9]{1,12}'
        self.maxmask = '[0-9]'
        tryCnt = 0
        while True:# this creates the VC_COMPRESSOR command options for this specific printer based on it's bed info
            try:
                self.sock.sendto(self.encodeCmd(self.CMD_PRINTER_INFO), (self.ipaddr, self.PORT))
                message, address = self.sock.recvfrom(self.BUFSIZE)
                pattern = re.compile(self.datamask) # TODO: use this
                msg = message.decode('utf-8','ignore')
                if('X' not in msg or 'Y' not in msg or 'Z' not in msg ):
                    continue
                msg = msg.replace('\r','')
                msg = msg.replace('\n', '')
                msgs = msg.split(' ')
                logger.info(msg)
                e_mm_per_step = z_mm_per_step = y_mm_per_step = x_mm_per_step = '0.0'
                s_machine_type = s_x_max = s_y_max = s_z_max = '0.0'
                for item in msgs:
                    _ = item.split(':')
                    if(len(_) == 2):
                        id = _[0]
                        value = _[1]
                        logger.info(_)
                        if id == 'X':
                            x_mm_per_step = value
                        elif id == 'Y':
                            y_mm_per_step = value
                        elif id == 'Z':
                           z_mm_per_step = value
                        elif id == 'E':
                            e_mm_per_step = value
                        elif id == 'T':
                            _ = value.split('/')
                            if len(_) == 5:
                                s_machine_type = _[0]
                                s_x_max = _[1]
                                s_y_max = _[2]
                                s_z_max = _[3]
                        elif id == 'U':
                            self._file_encode = value.replace("'","")
                cmd = path.normpath(self.VC_COMPRESS) + " \"" + self.gcodeFile + "\" " + x_mm_per_step + " " + y_mm_per_step + " " + z_mm_per_step + " " + e_mm_per_step\
                         + ' \"' + path.normpath(".") + '\" ' + s_x_max + " " + s_y_max + " " + s_z_max + " " + s_machine_type
                logger.info(cmd)
                ret = subprocess.Popen(cmd,stdout=subprocess.PIPE,shell=True)
                logger.info(ret.stdout.read().decode("utf-8", 'ignore'))
                break
            except timeout:
                tryCnt += 1
                if(tryCnt > 5):
                    self._result = self.CONNECT_TIMEOUT
                    logger.error("Error trying to contact printer to determine print characteristcs.")
                    break
            except:
                logger.error("Serious problem attempting compression")
                traceback.print_exc()
                break

    def startPrint(self):
        self.sock.settimeout(2)
        try:
            #cmd = self.CMD_PRINT_SD + '":' + self.fileName + '" I1'  # I1 option purpose is unknown? try removing?
            cmd = 'M6030 ":' + self.fileName + '" I1'
            self.sock.sendto(self.encodeCmd(cmd), (self.ipaddr, self.PORT))
            message, address = self.sock.recvfrom(self.RECVBUF)
        except:
            logger.error("Serious problems starting the print:")
            traceback.print_exc()

    def getPrinterInfo(self):
        self.sock.settimeout(2)
        try:
            cmd = self.CMD_STATUS
            self.sock.sendto(self.encodeCmd(cmd), (self.ipaddr, self.PORT))
            message, address = self.sock.recvfrom(self.RECVBUF)
            mess = message.decode('utf-8','replace')
            return mess
        except:
            logger.error("problem getting printer info")
            traceback.print_exc()

    def getFirmwareInfo(self):
        self.sock.settimeout(self.CONNECT_TIMEOUT)
        try:
            cmd = self.CMD_FIRMWARE
            self.sock.sendto(self.encodeCmd(cmd), (self.ipaddr, self.PORT))
            message, address = self.sock.recvfrom(self.RECVBUF)
            return message.decode('utf-8','replace')
        except:
            logger.error("problem getting printer info")
            traceback.print_exc()

def ReadFileChunk(filename, startPos, endPos):


    return


if __name__ == '__main__':
    printDev = WiFiDevice()
    printDev.dirPath = os.path.dirname(os.path.realpath(__file__))
    os.chdir(printDev.dirPath)
    printDev.ipaddr = sys.argv[1]
    printDev.name = 'Xpro'  # TODO: this should be detected at initialization instead of hardcoded
    printDev.gcodeFile = sys.argv[2]
    logger.info("Printer Info\r\n------------------")
    logger.info("board/firmware info: " + printDev.getPrinterInfo())
    logger.info("firmware version: " + printDev.getFirmwareInfo())
    printDev.fileName = printDev.gcodeFile + '.tz'   
    logger.info('File 1: ' +  printDev.gcodeFile + 'File 2: ' + printDev.fileName)
    printDev.dataCompressThread()
    time.sleep(2)
    logger.info('3D Printer ' + printDev.name + ' IP address: ' + printDev.ipaddr)
    printDev.sendStartWriteSd()
    time.sleep(2)
    printDev.sendFile()
    printDev.sendEndWriteSd()
    if len(sys.argv) >= 4 and sys.argv[3] == 'yes':
        printDev.startPrint()
