
import sys
import os
import time
import signal

# Add include directory to path to find tux_driver.py
current_dir = os.path.dirname(os.path.abspath(__file__))
include_dir = os.path.join(current_dir, '../include')
sys.path.append(include_dir)

from tux_driver import *

def signal_handler(sig, frame):
    print("\nExiting...")
    tux_drv.Stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def on_status_event(status):
    # Enable status printing to see if we are getting data from the bot
    status_struct = tux_drv.GetStatusStruct(status)
    print(f"Status Event: {status_struct['name']} = {status_struct['value']}")
    
    if status_struct['name'] == 'radio_state':
        if status_struct['value']:
            print(">>> RF LINK ACTIVE <<<")
        else:
            print(">>> RF LINK LOST <<<")

def on_dongle_connected():
    print("Dongle connected! Waiting for RF link...")
    # Give some time for RF to establish if needed
    time.sleep(2)
    
    # Check if we have RF
    # Note: This is an indirect check, ideally we rely on status events
    
    print("Resetting positions...")
    tux_drv.ResetPositions()
    
    print("Testing Flippers...")
    # FLIPPERS:ON:4:OPEN
    tux_drv.PerformCommand(0, "FLIPPERS:ON:4:OPEN")
    time.sleep(2)
    tux_drv.PerformCommand(0, "FLIPPERS:OFF")
    time.sleep(0.5)
    
    print("Testing Mouth...")
    # MOUTH:OPEN
    tux_drv.PerformCommand(0, "MOUTH:OPEN")
    time.sleep(1)
    # MOUTH:CLOSE
    tux_drv.PerformCommand(0, "MOUTH:CLOSE")
    time.sleep(1)
    
    print("Testing Eyes...")
    # EYES:OPEN
    tux_drv.PerformCommand(0, "EYES:OPEN")
    time.sleep(1)
    # EYES:CLOSE
    tux_drv.PerformCommand(0, "EYES:CLOSE")
    time.sleep(1)

    print("Testing Spinning...")
    # SPINNING:LEFT_ON:2
    tux_drv.PerformCommand(0, "SPINNING:LEFT_ON:2")
    time.sleep(3)
    
    print("Test sequence complete.")
    tux_drv.Stop()
    sys.exit(0)

if __name__ == "__main__":
    lib_path = os.path.join(current_dir, '../unix/libtuxdriver.so')
    
    if not os.path.exists(lib_path):
        print(f"Error: Library not found at {lib_path}")
        print("Please build the project first (cd unix && make)")
        sys.exit(1)

    print(f"Loading library from {lib_path}")
    tux_drv = TuxDrv(lib_path)
    
    tux_drv.SetLogLevel(LOG_LEVEL_DEBUG)
    tux_drv.SetStatusCallback(on_status_event)
    tux_drv.SetDongleConnectedCallback(on_dongle_connected)
    
    print("Starting Tux Driver...")
    print("Please ensure the USB dongle is plugged in and the penguin is active.")
    tux_drv.Start()
    
    # Keep main thread alive waiting for callbacks
    while True:
        time.sleep(1)
