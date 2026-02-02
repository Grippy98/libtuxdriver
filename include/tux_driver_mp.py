# Tux Droid - Driver (MicroPython ffi version)
import os
import sys
import ffi

E_TUXDRV_BEGIN                      = 256
E_TUXDRV_NOERROR                    = 0
E_TUXDRV_PARSERISDISABLED           = E_TUXDRV_BEGIN
E_TUXDRV_INVALIDCOMMAND             = E_TUXDRV_BEGIN + 1
E_TUXDRV_STACKOVERFLOW              = E_TUXDRV_BEGIN + 2
E_TUXDRV_FILEERROR                  = E_TUXDRV_BEGIN + 3
E_TUXDRV_BADWAVFILE                 = E_TUXDRV_BEGIN + 4
E_TUXDRV_INVALIDIDENTIFIER          = E_TUXDRV_BEGIN + 5
E_TUXDRV_INVALIDNAME                = E_TUXDRV_BEGIN + 6
E_TUXDRV_INVALIDPARAMETER           = E_TUXDRV_BEGIN + 7
E_TUXDRV_BUSY                       = E_TUXDRV_BEGIN + 8
E_TUXDRV_WAVSIZEEXCEDED             = E_TUXDRV_BEGIN + 9

SW_ID_FLIPPERS_POSITION             = 0
SW_ID_FLIPPERS_REMAINING_MVM        = 1
SW_ID_SPINNING_DIRECTION            = 2
SW_ID_SPINNING_REMAINING_MVM        = 3
SW_ID_LEFT_WING_BUTTON              = 4
SW_ID_RIGHT_WING_BUTTON             = 5
SW_ID_HEAD_BUTTON                   = 6
SW_ID_REMOTE_BUTTON                 = 7
SW_ID_MOUTH_POSITION                = 8
SW_ID_MOUTH_REMAINING_MVM           = 9
SW_ID_EYES_POSITION                 = 10
SW_ID_EYES_REMAINING_MVM            = 11
SW_ID_DESCRIPTOR_COMPLETE           = 12
SW_ID_RF_STATE                      = 13
SW_ID_DONGLE_PLUG                   = 14
SW_ID_CHARGER_STATE                 = 15
SW_ID_BATTERY_LEVEL                 = 16
SW_ID_BATTERY_STATE                 = 17
SW_ID_LIGHT_LEVEL                   = 18
SW_ID_LEFT_LED_STATE                = 19
SW_ID_RIGHT_LED_STATE               = 20
SW_ID_CONNECTION_QUALITY            = 21
SW_ID_AUDIO_FLASH_PLAY              = 22
SW_ID_AUDIO_GENERAL_PLAY            = 23
SW_ID_FLASH_PROG_CURR_TRACK         = 24
SW_ID_FLASH_PROG_LAST_TRACK_SIZE    = 25
SW_ID_TUXCORE_SYMBOLIC_VERSION      = 26
SW_ID_TUXAUDIO_SYMBOLIC_VERSION     = 27
SW_ID_FUXUSB_SYMBOLIC_VERSION       = 28
SW_ID_FUXRF_SYMBOLIC_VERSION        = 29
SW_ID_TUXRF_SYMBOLIC_VERSION        = 30
SW_ID_DRIVER_SYMBOLIC_VERSION       = 31
SW_ID_SOUND_REFLASH_BEGIN           = 32
SW_ID_SOUND_REFLASH_END             = 33
SW_ID_SOUND_REFLASH_CURRENT_TRACK   = 34
SW_ID_EYES_MOTOR_ON                 = 35
SW_ID_MOUTH_MOTOR_ON                = 36
SW_ID_FLIPPERS_MOTOR_ON             = 37
SW_ID_SPIN_LEFT_MOTOR_ON            = 38
SW_ID_SPIN_RIGHT_MOTOR_ON           = 39
SW_ID_FLASH_SOUND_COUNT             = 40

SW_NAME_DRIVER = [
    "flippers_position", "flippers_remaining_movements", "spinning_direction",
    "spinning_remaining_movements", "left_wing_button", "right_wing_button",
    "head_button", "remote_button", "mouth_position", "mouth_remaining_movements",
    "eyes_position", "eyes_remaining_movements", "descriptor_complete",
    "radio_state", "dongle_plug", "charger_state", "battery_level",
    "battery_state", "light_level", "left_led_state", "right_led_state",
    "connection_quality", "audio_flash_play", "audio_general_play",
    "flash_programming_current_track", "flash_programming_last_track_size",
    "tuxcore_symbolic_version", "tuxaudio_symbolic_version",
    "fuxusb_symbolic_version", "fuxrf_symbolic_version",
    "tuxrf_symbolic_version", "driver_symbolic_version",
    "sound_reflash_begin", "sound_reflash_end", "sound_reflash_current_track",
    "eyes_motor_on", "mouth_motor_on", "flippers_motor_on",
    "spin_left_motor_on", "spin_right_motor_on", "sound_flash_count"
]

LOG_LEVEL_DEBUG             = 0
LOG_LEVEL_INFO              = 1
LOG_LEVEL_WARNING           = 2
LOG_LEVEL_ERROR             = 3
LOG_LEVEL_NONE              = 4

LOG_TARGET_TUX              = 0
LOG_TARGET_SHELL            = 1

class TuxDrv(object):
    def __init__(self, library_path):
        self.tux_driver_lib = None
        self.__status_cb = None
        self.__dongle_conn_cb = None
        self.__dongle_disconn_cb = None
        
        try:
            self.tux_driver_lib = ffi.open(library_path)
            # Define functions
            self._start = self.tux_driver_lib.func("v", "TuxDrv_Start", "")
            self._stop = self.tux_driver_lib.func("v", "TuxDrv_Stop", "")
            self._perform_cmd = self.tux_driver_lib.func("i", "TuxDrv_PerformCommand", "ds")
            self._reset_pos = self.tux_driver_lib.func("v", "TuxDrv_ResetPositions", "")
            self._set_log_level = self.tux_driver_lib.func("v", "TuxDrv_SetLogLevel", "b")
            
            # Callbacks
            self._set_status_cb = self.tux_driver_lib.func("v", "TuxDrv_SetStatusCallback", "C")
            self._set_dongle_conn_cb = self.tux_driver_lib.func("v", "TuxDrv_SetDongleConnectedCallback", "C")
            self._set_dongle_disconn_cb = self.tux_driver_lib.func("v", "TuxDrv_SetDongleDisconnectedCallback", "C")
            
            # Non-blocking functions
            self._init_nonblocking = self.tux_driver_lib.func("v", "TuxDrv_InitNonBlocking", "")
            self._poll_once = self.tux_driver_lib.func("v", "TuxDrv_PollOnce", "")
            self._stop_nonblocking = self.tux_driver_lib.func("v", "TuxDrv_StopNonBlocking", "")
            
        except Exception as e:
            print(f"Error loading libtuxdriver: {e}")
            self.tux_driver_lib = None

    def SetStatusCallback(self, funct):
        if not self.tux_driver_lib: return
        self.__status_cb = ffi.callback("v", funct, "s")
        self._set_status_cb(self.__status_cb)

    def SetDongleConnectedCallback(self, funct):
        if not self.tux_driver_lib: return
        self.__dongle_conn_cb = ffi.callback("v", funct, "")
        self._set_dongle_conn_cb(self.__dongle_conn_cb)

    def SetDongleDisconnectedCallback(self, funct):
        if not self.tux_driver_lib: return
        self.__dongle_disconn_cb = ffi.callback("v", funct, "")
        self._set_dongle_disconn_cb(self.__dongle_disconn_cb)

    def Init(self):
        """Initialize the driver manually without starting the blocking loop."""
        if not self.tux_driver_lib: return False
        try:
            self._init_nonblocking()
            return True
        except:
            return False

    def Poll(self):
        """Poll for USB events - should be called periodically."""
        if not self.tux_driver_lib: return
        try:
            self._poll_once()
        except:
            pass

    def Start(self):
        """Start the driver - simplified version without threading."""
        if not self.tux_driver_lib: return
        # Just initialize, don't start the blocking loop
        return self.Init()

    def Stop(self):
        if not self.tux_driver_lib: return
        try:
            self._stop_nonblocking()
        except:
            pass

    def PerformCommand(self, delay, command):
        if not self.tux_driver_lib: return E_TUXDRV_PARSERISDISABLED
        return self._perform_cmd(float(delay), command)

    def ResetPositions(self):
        if not self.tux_driver_lib: return
        self._reset_pos()

    def SetLogLevel(self, level=LOG_LEVEL_INFO):
        if not self.tux_driver_lib: return
        self._set_log_level(level)

    def TokenizeStatus(self, status):
        if isinstance(status, bytes):
            status = status.decode('utf-8')
        result = status.split(":")
        if len(result) == 1 and result[0] == '':
            result = []
        return result

    def GetStatusStruct(self, status):
        result = {'name': "None", 'value': None, 'delay': 0.0, 'type': 'string'}
        status_s = self.TokenizeStatus(status)
        if len(status_s) < 4: return result
        
        result['name'] = status_s[0]
        result['type'] = status_s[1]
        result['delay'] = float(status_s[3])
        
        val_str = status_s[2]
        if result['type'] in ['uint8', 'int8', 'int', 'float']:
            result['value'] = float(val_str) if '.' in val_str else int(val_str)
        elif result['type'] == 'bool':
            result['value'] = val_str.lower() == 'true' or val_str == '1'
        else:
            result['value'] = val_str
            
        return result
