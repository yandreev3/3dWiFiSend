#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import logging
import time
from socket import *
import struct

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import re

import subprocess
import os
from os import path

class WiFiDevice():
    CMD_STARTWRITE_SD = "M28 "
    CMD_ENDWRITE_SD = "M29 "
    CMD_GETFILELIST = "M20 "
    PORT = 3000
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
        self.sock.settimeout(3)
        self._file_encode = 'utf-8'

    def __str__(self):
        s = ('Device addr:' + self.ipaddr + '==' + self.name)
        return s

    def encodeCmd(self,cmd):
        return cmd.encode(self._file_encode, 'ignore')

    def decodeCmd(self,cmd):
        return cmd.decode(self._file_encode,'ignore')

    def sendStartWriteSd(self):
        cmd = self.CMD_STARTWRITE_SD + self.fileName
        logger.info("Start write to SD: " + cmd)
        self.sock.sendto(self.encodeCmd(cmd), (self.ipaddr, self.PORT))
        message, address = self.sock.recvfrom(self.RECVBUF)
        message = message.decode('utf-8','replace')
        logger.info("Start write to SD result: " +  message)
        return

    def sendEndWriteSd(self):
        cmd = self.CMD_ENDWRITE_SD + self.fileName
        logger.info("End write to SD: " + cmd)
        self.sock.sendto(self.encodeCmd(cmd), (self.ipaddr, self.PORT))
        message, address = self.sock.recvfrom(self.RECVBUF)
        message = message.decode('utf-8','replace')
        logger.info("End write to SD result: " +  message)
        return

    def sendGetFileList(self):
        cmd = self.CMD_GETFILELIST
        logger.info("Get List of Files: " + cmd)
        self.sock.sendto(self.encodeCmd(cmd), (self.ipaddr, self.PORT))
        message, address = self.sock.recvfrom(self.RECVBUF)
        message = message.decode('utf-8','replace')
        logger.info("Get list of files result: " +  message)
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
        while True:#(send_ip):
            try:
#                self.sock.settimeout(2)
#                Logger.log("i", self._targetIP)
                self.sock.sendto(b"M4001", (self.ipaddr, self.PORT))
                message, address = self.sock.recvfrom(self.BUFSIZE)
                pattern = re.compile(self.datamask)
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
                cmd = path.normpath(".\VC_compress_gcode.exe") + " \"" + self.gcodeFile + "\" " + x_mm_per_step + " " + y_mm_per_step + " " + z_mm_per_step + " " + e_mm_per_step\
                         + ' \"' + path.normpath(".") + '\" ' + s_x_max + " " + s_y_max + " " + s_z_max + " " + s_machine_type
                logger.info(cmd)
                ret = subprocess.Popen(cmd,stdout=subprocess.PIPE,shell=True)
                logger.info(ret.stdout.read().decode("utf-8", 'ignore'))
                break
            except timeout:
                tryCnt += 1
                if(tryCnt > 5):
                    self._result = MyWifiSend.CONNECT_TIMEOUT
                    break
            except:
                traceback.print_exc()
                break

    def startPrint(self):
        self.sock.settimeout(2)
        try:
            cmd = 'M6030 ":' + self.fileName + '" I1'
            self.sock.sendto(self.encodeCmd(cmd), (self.ipaddr, self.PORT))
            message, address = self.sock.recvfrom(self.RECVBUF)
        except:
            traceback.print_exc()

def ReadFileChunk(filename, startPos, endPos):


    return


if __name__ == '__main__':
    printDev = WiFiDevice()
    printDev.dirPath = os.path.dirname(os.path.realpath(__file__))
    os.chdir(printDev.dirPath)
    printDev.ipaddr = sys.argv[1]
    printDev.name = 'Xpro'
    printDev.gcodeFile = sys.argv[2]
    printDev.fileName = printDev.gcodeFile[2:] + '.tz'   
    printDev.dataCompressThread()
    time.sleep(2)
    logger.info('3D Printer ' + printDev.name + ' IP address: ' + printDev.ipaddr)
    printDev.sendStartWriteSd()
    time.sleep(2)
    printDev.sendFile()
    printDev.sendEndWriteSd()
    if len(sys.argv) >= 4 and sys.argv[3] == 'yes':
        printDev.startPrint()
