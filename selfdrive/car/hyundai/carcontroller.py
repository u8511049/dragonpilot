from selfdrive.car import apply_std_steer_torque_limits
from selfdrive.car.hyundai.hyundaican import create_lkas11, create_clu11
from selfdrive.car.hyundai.values import Buttons, SteerLimitParams
from opendbc.can.packer import CANPacker
from common.params import Params
params = Params()
from selfdrive.dragonpilot.dragonconf import dp_get_last_modified

class CarController():
  def __init__(self, dbc_name, CP, VM):
    self.apply_steer_last = 0
    self.car_fingerprint = CP.carFingerprint
    self.lkas11_cnt = 0
    self.cnt = 0
    self.last_resume_cnt = 0
    self.packer = CANPacker(dbc_name)
    self.steer_rate_limited = False

    # dragonpilot
    self.turning_signal_timer = 0
    self.dragon_enable_steering_on_signal = False
    self.dragon_lat_ctrl = True
    self.dp_last_modified = None
    self.lane_change_enabled = True

  def update(self, enabled, CS, frame, actuators, pcm_cancel_cmd, hud_alert):

    # dragonpilot, don't check for param too often as it's a kernel call
    if frame % 500 == 0:
      modified = dp_get_last_modified()
      if self.dp_last_modified != modified:
        self.dragon_lat_ctrl = False if params.get("DragonLatCtrl", encoding='utf8') == "0" else True
        if self.dragon_lat_ctrl:
          self.lane_change_enabled = False if params.get("LaneChangeEnabled", encoding='utf8') == "1" else False
          if not self.lane_change_enabled:
            self.dragon_enable_steering_on_signal = True if params.get("DragonEnableSteeringOnSignal", encoding='utf8') == "1" else False
          else:
            self.dragon_enable_steering_on_signal = False
        else:
          self.dragon_enable_steering_on_signal = False
        self.dp_last_modified = modified

    ### Steering Torque
    new_steer = actuators.steer * SteerLimitParams.STEER_MAX
    apply_steer = apply_std_steer_torque_limits(new_steer, self.apply_steer_last, CS.out.steeringTorque, SteerLimitParams)
    self.steer_rate_limited = new_steer != apply_steer

    if not enabled:
      apply_steer = 0

    steer_req = 1 if enabled else 0

    self.apply_steer_last = apply_steer

    can_sends = []

    # dragonpilot
    if enabled:
      if self.dragon_enable_steering_on_signal:
        if not CS.out.leftBlinker and not CS.out.rightBlinker:
          self.turning_signal_timer = 0
        else:
          self.turning_signal_timer = 100

        if self.turning_signal_timer > 0:
          self.turning_signal_timer -= 1
          steer_req = 0
      else:
        self.turning_signal_timer = 0

      if not self.dragon_lat_ctrl:
        steer_req = 0

    self.lkas11_cnt = self.cnt % 0x10
    self.clu11_cnt = self.cnt % 0x10

    can_sends.append(create_lkas11(self.packer, self.car_fingerprint, apply_steer, steer_req, self.lkas11_cnt,
                                   enabled, CS.lkas11, hud_alert, keep_stock=True))

    if pcm_cancel_cmd:
      can_sends.append(create_clu11(self.packer, CS.clu11, Buttons.CANCEL))
    elif CS.out.cruiseState.standstill and (self.cnt - self.last_resume_cnt) > 5:
      self.last_resume_cnt = self.cnt
      can_sends.append(create_clu11(self.packer, CS.clu11, Buttons.RES_ACCEL))

    self.cnt += 1

    return can_sends
