import ctypes
import time
import os

# Load library
lib = ctypes.CDLL("../unix/libtuxdriver.so")

# Callback types
STATUS_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_char_p)

def on_status(status):
    pass
    # print(f"STATUS: {status.decode('utf-8', errors='ignore')}")

status_cb = STATUS_CALLBACK(on_status)

print("Starting TuxDriver...")
lib.TuxDrv_SetLogLevel(3) # DEBUG
lib.TuxDrv_SetLogTarget(0) # SHELL
lib.TuxDrv_SetStatusCallback(status_cb)

lib.TuxDrv_Start()

print("Waiting for init (5s)...")
time.sleep(5)

print("Opening Eyes...")
lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:EYES:OPEN")
time.sleep(2)

print("Closing Eyes...")
lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:EYES:CLOSE")
time.sleep(2)

print("Done. Keeping alive for 5s...")
time.sleep(5)

lib.TuxDrv_Stop()
