
import sys
import os
import time
import threading

# Add include directory to path to find tux_driver.py
current_dir = os.path.dirname(os.path.abspath(__file__))
include_dir = os.path.join(current_dir, '../include')
sys.path.append(include_dir)

from tux_driver import *

rf_connected = False
dongle_connected = False
running = True

def on_status_event(status):
    global rf_connected
    # Enable status printing to see if we are getting data from the bot
    status_struct = tux_drv.GetStatusStruct(status)
    print(f"Status Event: {status_struct['name']} = {status_struct['value']}")
    
    if status_struct['name'] == 'radio_state':
        if status_struct['value']:
            print(">>> RF LINK ACTIVE <<<")
            rf_connected = True
        else:
            print(">>> RF LINK LOST <<<")
            rf_connected = False

def on_dongle_connected():
    global dongle_connected
    print("Dongle connected callback received.")
    dongle_connected = True
    # Don't sleep or block here! Return quickly.

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
    
    print("Starting Tux Driver in background thread...")
    t = threading.Thread(target=tux_drv.Start)
    t.daemon = True
    t.start()
    
    print("Waiting for Dongle...")
    wait_start = time.time()
    while not dongle_connected:
        time.sleep(0.1)
        if time.time() - wait_start > 5:
            print("Timed out waiting for dongle!")
            # Proceed anyway to see debug output
            break
            
    if dongle_connected:
        print("Dongle detected. Waiting for RF Link (press the button on Tux's head if needed)...")
        wait_start = time.time()
        while not rf_connected:
            time.sleep(0.5)
            if time.time() - wait_start > 15:
                print("Timed out waiting for RF Link! Trying comands anyway...")
                break
    
    print("Resetting positions...")
    tux_drv.ResetPositions()
    
    print("Testing Flippers...")
    tux_drv.PerformCommand(0, "TUX_CMD:FLIPPERS:ON:4:OPEN")
    time.sleep(2)
    tux_drv.PerformCommand(0, "TUX_CMD:FLIPPERS:OFF")
    time.sleep(0.5)
    
    print("Testing Mouth...")
    tux_drv.PerformCommand(0, "TUX_CMD:MOUTH:OPEN")
    time.sleep(1)
    tux_drv.PerformCommand(0, "TUX_CMD:MOUTH:CLOSE")
    time.sleep(1)
    
    print("Testing Eyes...")
    tux_drv.PerformCommand(0, "TUX_CMD:EYES:OPEN")
    time.sleep(1)
    tux_drv.PerformCommand(0, "TUX_CMD:EYES:CLOSE")
    time.sleep(1)

    print("Testing Spinning...")
    # Use ON_DURING for better visibility (spin for 3 seconds)
    tux_drv.PerformCommand(0, "TUX_CMD:SPINNING:LEFT_ON_DURING:3.0")
    time.sleep(4)
    
    print("Opening Eyes for final state...")
    tux_drv.PerformCommand(0, "TUX_CMD:EYES:OPEN")
    time.sleep(1)
    
    print("Test sequence complete.")
    tux_drv.Stop()
    t.join(timeout=2)
