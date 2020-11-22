#! /usr/bin/python3
import serial
import queue
import sys
import re
import threading
import traceback


shutdowndelay = 60
##Fix for turning off after 2:30 min even if turned on again
class bosecom(threading.Thread):

    __serialcommands = {
    "ON" : "KP 7",
    "OFF" : "KP 1",
    "MUTE" : "KP %53",
    "UP" : "KP %26",
    "DOWN" : "KP %27",
    "GETVOL" : "VG",
    "SETVOL" : "VS ",
    "SETDECIMAL" : "NB 10"
    }

    #private functions

    def __ExtractVolume(self, volume):
        match = re.search(r'[0-9]+', volume)
        return int(match.group(0))

    def __ConverttoPercent(self, volume):
        return round((100/self.max_volume) * volume)

    def __ConvertfromPercent(self, volume):
        return round((self.max_volume/100) * volume)

    def __SetVolume(self):
        self.sendqueue.put(["SETVOL", (self.__serialcommands["SETVOL"] + str(self.volume) + "\n")])

    def __sendCommand(self, command):
        self.ser.write(bytes(command + "\n", 'ascii'))
        return self.recievequeue.get(timeout=5)

    def __Serialsetup(self):
        with bosecom.lock:
            result = self.__sendCommand("CB")
            if(result.find('19200') == -1):
                self.logger.error("Bosecom: Baud rate response from Bose system was wrong!")
                sys.exit()
            self.__sendCommand(self.__serialcommands["SETDECIMAL"])
            result = self.__sendCommand(self.__serialcommands["GETVOL"])
            volume = self.__ExtractVolume(result)
            if(volume == None):
                self.logger.error("Bosecom: Error getting volume from system!")
                sys.exit()
            if(self.volume != volume):
                self.__SetVolume

    #Threading functions
    def recieveFunction(self):
        self.logger.debug("Bosecom: Recieve Thread started")
        data = ""
        while(True):
            if (self.ser.in_waiting>0):
                tmp = self.ser.read(1).decode('ascii')
                data += tmp
                if(tmp == ">"):
                    if(data.find("\n") == -1):
                        if(self.turnedOn):
                            self.turnedOn = False
                            self.TurnOn()
                    else:
                        self.recievequeue.put(data)
                    data = ""
    

    def TurnOfffunction(self):
        self.turnedOn = False
        self.sendqueue.put(["OFF", self.__serialcommands["OFF"]])
        self.logger.debug("Bosecom: Turn off send")
        self.turnOffpending = False

    def run(self):
        try:
            self.ser =  serial.Serial(self.device_port, 19200, timeout=20)
            #Start serial recieve thread
            self.recievethread.start()
            self.__Serialsetup()
            self.logger.info("Bosecom: Send thread started")
            while True:
                command = self.sendqueue.get()
                with bosecom.lock:
                    self.__sendCommand(command[1])
        except:
            traceback.print_exc()
            self.logger.error("Bosecom: Error in serial communication")
        finally:
            sys.exit()     


    #public functions
    def __init__(self, device_port, max_volume, returnqueue, logger):
        threading.Thread.__init__(self, daemon=True)

        #Threads
        bosecom.lock = threading.Lock()
        self.recievethread = threading.Thread(target=self.recieveFunction, daemon=True)
        self.turnoffthread = threading.Timer(shutdowndelay, self.TurnOfffunction)
        self.turnoffthread.daemon = True

        #Supplied vars
        self.max_volume = max_volume
        self.device_port = device_port
        self.cecqueue = returnqueue
        self.logger = logger

        #LocalVars
        self.sendqueue = queue.Queue()
        self.recievequeue = queue.Queue()
        self.isMuted = False
        self.turnedOn = True
        self.turnOffpending = False
        self.volume = 25

    #Callable functions

    def SetVolume(self, volume):
        volume = self.__ConvertfromPercent(volume)
        if(volume > self.max_volume):
            volume = self.max_volume
        self.volume = volume
    
    def GetVolume(self):
        self.sendqueue.put(["GETVOL", self.__serialcommands["GETVOL"]])
        return self.__ConverttoPercent(self.volume)

    def VolumeUp(self):
        if(self.volume < self.max_volume):
            self.volume += 1
            self.cecqueue.put(self.__ConverttoPercent(self.volume))
            self.sendqueue.put(["UP", self.__serialcommands["UP"]])
        else:
            self.cecqueue.put(self.__ConverttoPercent(self.volume))


    def VolumeDown(self):
        if(self.volume > 0):
            self.volume -= 1
            self.cecqueue.put(self.__ConverttoPercent(self.volume))
            self.sendqueue.put(["DOWN", self.__serialcommands["DOWN"]])
        else:
            self.cecqueue.put(self.__ConverttoPercent(self.volume))

    def Mute(self):
        self.isMuted = not self.isMuted
        if(self.isMuted):
            self.cecqueue.put(self.__ConverttoPercent(self.volume)+128)
        else:
            self.cecqueue.put(self.__ConverttoPercent(self.volume))
        self.sendqueue.put(["MUTE", self.__serialcommands["MUTE"]])


    def TurnOn(self):
        if(self.turnedOn == False):
            self.__Serialsetup()

        if(self.turnOffpending):
            self.turnoffthread.cancel()
            self.turnOffpending = False

        self.turnedOn = True
        self.isMuted = False
        self.sendqueue.put(["ON", self.__serialcommands["ON"]])
        self.__SetVolume()

    def TurnOff(self):
        self.turnoffthread = threading.Timer(shutdowndelay, self.TurnOfffunction)
        self.turnOffpending = True
        self.turnoffthread.daemon = True
        self.turnoffthread.start()
        self.logger.debug("Bosecom: Turn off timer started")

    

    def TogglePower(self):
        if(self.turnedOn):
            self.TurnOn()
        else:
            self.TurnOff()