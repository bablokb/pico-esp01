# -------------------------------------------------------------------------
# Deep-sleeping an ESP-01 coprocessor.
#
# Test program for deep-sleep mode of an esp-01. This breakout is an ideal
# coprocessor for a Raspberry Pi Pico.
#
# This program runs in 5 modes
#  - sleep:     esp-01 in deep-sleep mode
#  - idle:      esp-01 running, but not connected
#  - connected: esp-01 as wifi-client
#  - udp:       esp-01 opened udp-socket
#  - sending:   esp-01 sends UDP-messages
#
# Switching is done using two buttons which increment and decrement the
# current state.
#
# Additional output-pins signal the current state. Useful either for
# visualizing with LEDs, or e.g. to pass to a measurement-device like
# the Nordic PPK2.
#
# Author: Bernhard Bablok
# License: GPL3
#
# Website: https://github.com/bablokb/pico-esp01-sleep
#
# -------------------------------------------------------------------------

# --- constants   ---------------------------------------------------------

import board

PIN_TX  = board.GP0
PIN_RX  = board.GP1
PIN_RST = board.GP2
PIN_INC = board.GP27
PIN_DEC = board.GP26
PIN_LED = board.LED

STATE_SLEEP =  0
STATE_IDLE  =  1
STATE_CONN  =  2
STATE_UDP   =  3
STATE_SEND  =  4
PINS_STATE  = [board.GP5, board.GP6, board.GP7, board.GP8, board.GP9]

LED_TIME = 0.2

# --- imports   -----------------------------------------------------------

import time
start_time = time.monotonic()
import alarm
import busio
from   digitalio import DigitalInOut, Direction, Pull

from adafruit_espatcontrol import (
  adafruit_espatcontrol,
  adafruit_espatcontrol_wifimanager,
)

# Get wifi details and more from a secrets.py file
try:
  from secrets import secrets
except ImportError:
  print("WiFi secrets are kept in secrets.py, please add them there!")
  raise

# --- application class   ---------------------------------------------------

class App:
  """ application class """

  # --- constructor   -------------------------------------------------------

  def __init__(self):
    """ constructor """

    self._setup()
    self._state = STATE_IDLE
    self._state_pin[self._state].value = 1
  
  # --- hardware-setup   ----------------------------------------------------

  def _setup(self):
    """ setup hardware """

    uart = busio.UART(PIN_TX, PIN_RX, baudrate=115200, receiver_buffer_size=2048)
    rst_pin = DigitalInOut(PIN_RST)
    self._esp = adafruit_espatcontrol.ESP_ATcontrol(
      uart, 115200, reset_pin=rst_pin, rts_pin=None, debug=secrets["debugflag"]
    )

    self._inc_pin           = DigitalInOut(PIN_INC)
    self._inc_pin.direction = Direction.INPUT
    self._inc_pin.pull      = Pull.UP

    self._dec_pin           = DigitalInOut(PIN_DEC)
    self._dec_pin.direction = Direction.INPUT
    self._dec_pin.pull      = Pull.UP

    self._led_pin           = DigitalInOut(PIN_LED)
    self._led_pin.direction = Direction.OUTPUT

    self._state_pin = []
    for pinnr in PINS_STATE:
      pin           = DigitalInOut(pinnr)
      pin.direction = Direction.OUTPUT
      pin.value     = 0
      self._state_pin.append(pin)

  # --- blink   --------------------------------------------------------------

  def _blink(self):
    """ blink the onboard LED """

    self._led_pin.value = 1
    time.sleep(LED_TIME)
    self._led_pin.value = 0

  # --- connect to station   -------------------------------------------------

  def _connect_wifi(self):
    """ connect to AP """

    self._wifi = adafruit_espatcontrol_wifimanager.ESPAT_WiFiManager(
      self._esp,secrets,None
    )

    # try to connect
    while True:
      try:
        print("connecting to AP ... ",end='')
        self._wifi.connect()
        print("done")
        break
      except Exception as e:
        print("Failed:\n", e)
      continue

  # --- connect to UDP-server   ---------------------------------------------

  def _connect_udp(self):
    """ connect to UDP-server """
    
    while True:
      try:
        print(
          "connecting to UDP-server %s:%d ... " %
                             (secrets["remoteip"],secrets["remoteport"]),end='')
        if self._esp.socket_connect(adafruit_espatcontrol.ESP_ATcontrol.TYPE_UDP,
                                    secrets["remoteip"],secrets["remoteport"]):
          print("done")
          break
        else:
          time.sleep(1)
          continue
      except Exception as e:
        print("Failed:\n", e)
        continue

  # --- send to UDP-socket   ------------------------------------------------

  def _send(self):
    """ send UDP-packets """
    
    data = "%6.4f\n" % (1000*time.monotonic())
    #print("sending data: %s" % data)
    data = data.encode('utf-8')
    self._esp.socket_send(data)

  # --- handle increment-button   -------------------------------------------

  def _handle_inc(self):
    """ handle increment button """

    self._blink()
    if self._state == STATE_SLEEP:
      print("leave ESP-01 sleep")
      self._esp.hard_reset()
    elif self._state == STATE_IDLE:
      self._connect_wifi()
    elif self._state == STATE_CONN:
      self._connect_udp()
    elif self._state == STATE_UDP:
      print("starting to send data")

    self._blink()
    self._state_pin[self._state].value = 0
    self._state += 1
    self._state_pin[self._state].value = 1

  # --- handle decrement-button   -------------------------------------------

  def _handle_dec(self):
    """ handle decrement button """

    self._blink()
    if self._state == STATE_IDLE:
      print("enter ESP-01 sleep")
      self._esp.deep_sleep(0)
    elif self._state == STATE_CONN:
      print("disconnect from AP")
      self._esp.soft_reset()
    elif self._state == STATE_UDP:
      print("disconnect from UDP")
      self._esp.socket_disconnect()
    elif self._state == STATE_SEND:
      print("stop sending data")

    self._blink()
    self._state_pin[self._state].value = 0
    self._state -= 1
    self._state_pin[self._state].value = 1

  # --- main application loop   ---------------------------------------------

  def run(self):
    """ main application loop """

    print("starting in state IDLE")
    while True:
      if not self._inc_pin.value and self._state < STATE_SEND:
        self._handle_inc()
      elif not self._dec_pin.value and self._state > STATE_SLEEP:
        self._handle_dec()
      elif self._state == STATE_SEND:
        self._send()

# --- main program   --------------------------------------------------------

app = App()
app.run()
