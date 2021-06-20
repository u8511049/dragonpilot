#!/usr/bin/env python3
import os
import time
from common.params import Params
params = Params()
import cereal.messaging as messaging
from common.realtime import sec_since_boot
from selfdrive.dragonpilot.dragonconf import dp_get_last_modified

def main():
  thermal_sock = messaging.sub_sock('thermal')
  last_ts = 0
  secs = 0
  last_secs = None
  shutdown_at = 0
  started = False
  usb_online = False
  enabled = False
  last_enabled = None
  dp_last_modified = None
  while 1:
    cur_time = sec_since_boot()
    if cur_time - last_ts >= 10.:
      modified = dp_get_last_modified()
      if dp_last_modified != modified:
        enabled = True if params.get("DragonEnableAutoShutdown", encoding='utf8') == '1' else False
        if enabled:
          secs = int(params.get("DragonAutoShutdownAt", encoding='utf8')) * 60

        dp_last_modified = modified

      if enabled:
        msg = messaging.recv_sock(thermal_sock, wait=True)
        started = msg.thermal.started
        usb_online = msg.thermal.usbOnline

      if last_enabled != enabled or last_secs != secs or started or usb_online:
        shutdown_at = cur_time + secs

      last_enabled = enabled
      last_secs = secs
      last_ts = cur_time

    if enabled and not started and not usb_online and secs > 0 and cur_time >= shutdown_at:
      os.system('LD_LIBRARY_PATH="" svc power shutdown')
    time.sleep(10)

if __name__ == "__main__":
  main()
