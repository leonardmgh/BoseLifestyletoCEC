#! /usr/bin/python3
from time import time
import serialcom
import queue
import cec
import threading
import sys
import logging
import signal
from systemd.journal import JournaldLogHandler
import serialcom

class ceccom(threading.Thread):
  cecconfig = cec.libcec_configuration()
  lib = {}

  def run(self):
      self.logger.info("CECcom thread started")
      self.commandThread.start()
      while True:
          command = self.sendqueue.get()
          command = '{:x}'.format(command)
          command = '50:7A:' + command
          command = self.lib.CommandFromString(command)
          self.lib.Transmit(command)

  # create a new libcec_configuration
  def SetConfiguration(self):
    self.cecconfig.strDeviceName   = "BoseAudio"
    self.cecconfig.bActivateSource = 0
    self.cecconfig.deviceTypes.Add(cec.CEC_DEVICE_TYPE_AUDIO_SYSTEM)
    self.cecconfig.clientVersion = cec.LIBCEC_VERSION_CURRENT

  def SetLogCallback(self, callback):
    self.cecconfig.SetLogCallback(callback)

  def SetKeyPressCallback(self, callback):
    self.cecconfig.SetKeyPressCallback(callback)

  def SetCommandCallback(self, callback):
    self.cecconfig.SetCommandCallback(callback)

  # detect an adapter and return the com port path
  def DetectAdapter(self):
    retval = None
    adapters = self.lib.DetectAdapters()
    for adapter in adapters:
      self.logger.debug("found a CEC adapter:")
      self.logger.debug("port:     " + adapter.strComName)
      self.logger.debug("vendor:   " + hex(adapter.iVendorId))
      self.logger.debug("product:  " + hex(adapter.iProductId))
      retval = adapter.strComName
    return retval

  def getTV(self):
    self.logger.info("Getting TV address")
    addresses = self.lib.GetActiveDevices()
    x = 0
    goNext = True
    while goNext:
      if addresses.IsSet(x):
        if(self.lib.LogicalAddressToString(x) == "TV"):
          self.tv = x
          goNext = False
      x += 1
      if x > 15:
        goNext = False
  
  def getTVPower(self):
    self.logger.info("Getting TV power status")
    power = self.lib.GetDevicePowerStatus(self.tv)
    if(power == cec.CEC_POWER_STATUS_ON or power == cec.CEC_POWER_STATUS_IN_TRANSITION_STANDBY_TO_ON):
      self.tv_power = True
    else:
      self.tv_power = False

  # initialise libCEC
  def InitLibCec(self):
    self.lib = cec.ICECAdapter.Create(self.cecconfig)
    # print libCEC version and compilation information
    self.logger.debug("libCEC version " + self.lib.VersionToString(self.cecconfig.serverVersion) + " loaded: " + self.lib.GetLibInfo())

    # search for adapters
    adapter = self.DetectAdapter()
    if adapter == None:
      self.logger.info("No adapters found")
    else:
      if self.lib.Open(adapter):
        self.logger.info("connection opened")
        self.getTV()
        self.getTVPower()
        if(self.tv_power):
          ceccom.bosecom.TurnOn()
        #GET tv power
      else:
        print("failed to open a connection to the CEC adapter")

  # logging callback
  def LogCallback(self, level, time, message):
    breakprogram = False
    if level == cec.CEC_LOG_ERROR:
      breakprogram = True
      printcall = self.logger.error
    elif level == cec.CEC_LOG_WARNING:
      printcall = self.logger.warning
    elif level == cec.CEC_LOG_NOTICE:
      printcall = self.logger.info
    elif level == cec.CEC_LOG_TRAFFIC:
      printcall = self.logger.debug
    elif level == cec.CEC_LOG_DEBUG:
      printcall = self.logger.debug

    printcall("LIBCEC:" + message)
    if(breakprogram):
      sys.exit()
    return 0

  #  # key press callback
  # def KeyPressCallback(self, key, duration):
  #   print("[Key press recieved] " + key)
  #   return 0

  # command received callback
  def CommandCallback(self, cmd):
    self.logger.debug("Command recieved: " + cmd)
    self.commandQueue.put(cmd)
    return 0

  def CommandQueueHandler(self):
    while True:
      cmd = self.commandQueue.get()
      # cmd = re.search('(?<=>> )(.+)', cmd)
      # cmd = cmd.group(0)
      if(cmd == '>> 05:44:41'):
          ceccom.bosecom.VolumeUp()
          self.logger.info("Volume UP command recieved")
      elif(cmd == '>> 05:44:42'):
          ceccom.bosecom.VolumeDown()
          self.logger.info("Volume Down command recieved")
      elif(cmd == '>> 0f:36'):
          ceccom.bosecom.TurnOff()
          self.logger.info("Volume TurnOff command recieved")
      elif(cmd == '>> 05:44:43'):
          ceccom.bosecom.Mute()
          self.logger.info("Volume Mute command recieved")
      elif(cmd == '>> 0f:84:00:00:00'):
          ceccom.bosecom.TurnOn()
          self.logger.info("Turn On command recieved")


  def __init__(self, new_queue, bosecomobj, logger):
    threading.Thread.__init__(self, daemon=True)
    self.commandQueue = queue.Queue()
    self.SetConfiguration()
    ceccom.bosecom = bosecomobj
    self.sendqueue = new_queue
    self.logger = logger
    self.commandThread = threading.Thread(target=self.CommandQueueHandler, daemon=True)

# logging callback
def log_callback(level, time, message):
  return lib.LogCallback(level, time, message)

# # key press callback
# def key_press_callback(key, duration):
#   return lib.KeyPressCallback(key, duration)

# command callback
def command_callback(cmd):
  return lib.CommandCallback(cmd)

def exitfunction(signum, frame):
    sys.exit()

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, exitfunction)
    logger = logging.getLogger("CECCOM")
    journald_handler = JournaldLogHandler()
    journald_handler.setFormatter(logging.Formatter(
    '[%(levelname)s] %(message)s'
    ))
    logger.addHandler(journald_handler)
    logger.setLevel(logging.DEBUG)
    # initialise libCEC
    cecqueue = queue.Queue()
    exception = False
    bosecomobj = serialcom.bosecom('/dev/ttyAMA0', 50, cecqueue, logger)
    lib = ceccom(cecqueue, bosecomobj, logger)
    lib.SetLogCallback(log_callback)
    # Somehow this function isn't working
    # lib.SetKeyPressCallback(key_press_callback)
    lib.SetCommandCallback(command_callback)
    lib.daemon = True
    bosecomobj.daemon = True
    lib.start()
    bosecomobj.start()
    lib.InitLibCec()
    try:
      while True:
        lib.join()
    except (KeyboardInterrupt, SystemExit):
      sys.exit()    