import sys
import os
import queue
import vosk
import json
import threading
import time
import ctypes
import random
import subprocess

# Add include directory to path to find tux_driver.py
current_dir = os.path.dirname(os.path.abspath(__file__))
include_dir = os.path.join(current_dir, '../include')
sys.path.append(include_dir)

from tux_driver import *

# Audio Config
SAMPLE_RATE = 16000
BLOCK_SIZE = 8000
q = queue.Queue()

# LLM Config
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    print("Loading SmolLM2-135M-Instruct (Optimizing for low RAM)...")
    checkpoint = "HuggingFaceTB/SmolLM2-135M-Instruct"
    tokenizer = AutoTokenizer.from_pretrained(checkpoint)
    
    # Load in bfloat16 to save RAM, move to CPU explicitly
    llm_model = AutoModelForCausalLM.from_pretrained(
        checkpoint, 
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True
    )
    llm_model.eval() # Disable dropout etc for inference
    torch.set_grad_enabled(False) # Save memory during generation
    print("LLM Loaded.")
except Exception as e:
    print(f"Warning: Could not load LLM optimally: {e}")
    llm_model = None

# TTS Config
# Using espeak via subprocess for better thread performance

# Tux Global State
tux_drv = None
mouth_thread = None
speaking = False
dongle_connected = False
link_connected = False

def on_dongle_connected():
    global dongle_connected
    print(">> Dongle Connected!")
    dongle_connected = True

def on_status_event(status):
    global link_connected
    try:
        status_struct = tux_drv.GetStatusStruct(status)
        if status_struct['name'] == 'radio_state':
            if status_struct['value']:
                print(">> RF Link Established!")
                link_connected = True
            else:
                print(">> RF Link Lost.")
                link_connected = False
    except Exception as e:
        # Fallback to string check if struct fails
        if isinstance(status, bytes):
            status = status.decode('utf-8')
        if "rf_link:CONNECTED" in status or "radio_state:1" in status:
            print(">> RF Link Established (Fallback)!")
            link_connected = True

def speech_animator():
    global speaking
    
    print(">> Animator Started")
    while speaking:
        # print(">> Animator Loop") # Debug too much
        # Open Mouth
        tux_drv.PerformCommand(0, "TUX_CMD:MOUTH:OPEN")
        
        # Randomly flap flippers (30% chance)
        if random.random() < 0.3: 
             # UP/DOWN is snappier than the macro ON command for doing it while speaking
             if random.random() < 0.5:
                 tux_drv.PerformCommand(0, "TUX_CMD:FLIPPERS:UP")
             else:
                 tux_drv.PerformCommand(0, "TUX_CMD:FLIPPERS:DOWN")
             
        # Randomly blink eyes (20% chance)
        if random.random() < 0.2: 
             tux_drv.PerformCommand(0, "TUX_CMD:EYES:CLOSE")
             time.sleep(0.1)
             tux_drv.PerformCommand(0, "TUX_CMD:EYES:OPEN")

        # Randomly pulse LEDs (10% chance)
        if random.random() < 0.1:
            tux_drv.PerformCommand(0, "TUX_CMD:LED:PULSE:LED_BOTH,4,10,1,1,1,10,1")

        time.sleep(0.2)
        if not speaking: break
        
        # Close Mouth
        tux_drv.PerformCommand(0, "TUX_CMD:MOUTH:CLOSE")
        time.sleep(0.2)
        
    # Ensure closed and reset
    try:
        tux_drv.PerformCommand(0, "TUX_CMD:MOUTH:CLOSE")
        tux_drv.PerformCommand(0, "TUX_CMD:FLIPPERS:DOWN")
        tux_drv.PerformCommand(0, "TUX_CMD:EYES:OPEN")
        tux_drv.PerformCommand(0, "TUX_CMD:LED:ON:LED_BOTH,1.0")
    except:
        pass

def tux_say(text):
    global speaking, mouth_thread
    print(f"Tux says: {text}")
    
    speaking = True
    mouth_thread = threading.Thread(target=speech_animator)
    mouth_thread.start()
    
    try:
        # Use espeak-ng command line - s 150 is speed
        subprocess.run(["espeak-ng", "-s", "150", text], check=True)
    except Exception as e:
        print(f"TTS Error: {e}")
        
    speaking = False
    if mouth_thread.is_alive():
        mouth_thread.join()

def main():
    global tux_drv, dongle_connected, link_connected
    
    # 1. Setup Tux Driver
    lib_path = os.path.join(current_dir, '../unix/libtuxdriver.so')
    if not os.path.exists(lib_path):
        print("Error: libtuxdriver.so not found. Run 'make' in unix/ folder.")
        sys.exit(1)
        
    tux_drv = TuxDrv(lib_path)
    tux_drv.SetLogLevel(LOG_LEVEL_DEBUG) # ENABLE DEBUG LOGS
    
    # Setup Callbacks
    tux_drv.SetDongleConnectedCallback(on_dongle_connected)
    tux_drv.SetStatusCallback(on_status_event)
    
    print("Starting Tux Driver (Waiting for connection)...")
    t = threading.Thread(target=tux_drv.Start)
    t.daemon = True
    t.start()
    
    # 2. Wait for HW connection
    print("Waiting for Hardware (Check Tux Droid is ON)...")
    timeout = 15
    start_wait = time.time()
    while (not dongle_connected or not link_connected) and (time.time() - start_wait < timeout):
        time.sleep(0.1)
        
    if not dongle_connected:
        print("FAILED: Dongle not detected. Check USB connection.")
        sys.exit(1)
    if not link_connected:
        print("FAILED: RF Link not established. Is Tux switched ON?")
        sys.exit(1)
        
    print("Hardware Ready. Testing movement...")
    tux_drv.ResetPositions()
    # Test a simple movement
    tux_drv.PerformCommand(0, "TUX_CMD:EYES:OPEN")
    time.sleep(1)
    tux_drv.PerformCommand(0, "TUX_CMD:EYES:CLOSE")
    time.sleep(1)
    tux_drv.PerformCommand(0, "TUX_CMD:EYES:OPEN")
    print("Movement test complete.")
    
    # 3. Setup Vosk
    try:
        from vosk import Model, KaldiRecognizer
        if not os.path.exists("model"):
            print("Loading Model (Auto-downloading if necessary)...")
            model = Model(lang="en-us") 
        else:
            model = Model("model")
        rec = KaldiRecognizer(model, SAMPLE_RATE)
    except Exception as e:
        print(f"Vosk error: {e}")
        sys.exit(1)

    # 3. Microhone Loop
    print("\n-----------------------------")
    print(" LISTENING... Say 'Hey Tux' or 'Pentax'")
    print("-----------------------------\n")

    try:
        import pyaudio
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE, input=True, frames_per_buffer=8000)
        stream.start_stream()

        while True:
            data = stream.read(4000, exception_on_overflow=False)
            if rec.AcceptWaveform(data):
                res = json.loads(rec.Result())
                text = res.get('text', '')
                
                if text:
                    print(f"Heard: {text}")
                    # Fuzzy match wake word
                    wake_words = ["hey tux", "hey tax", "hey text", "hey ducks", "hey tucks", "pentax", "pan text", "pen tax", "he tucks"]
                    
                    found_wake_word = None
                    lower_text = text.lower()
                    for w in wake_words:
                        if w in lower_text:
                            found_wake_word = w
                            break
                            
                    if found_wake_word:
                        print(f">> Wake Word Detected: '{found_wake_word}' <<")
                        
                        idx = lower_text.find(found_wake_word)
                        prompt = text[idx + len(found_wake_word):].strip()
                        
                        if not prompt:
                             prompt = "Hello"
                             
                        print(f"Prompting LLM: {prompt}")
                        # OPEN/CLOSE is safer than invalid BLINK
                        tux_drv.PerformCommand(0, "TUX_CMD:EYES:CLOSE")
                        time.sleep(0.2)
                        tux_drv.PerformCommand(0, "TUX_CMD:EYES:OPEN")
                        
                        if llm_model:
                            try:
                                messages = [{"role": "user", "content": prompt}]
                                input_text = tokenizer.apply_chat_template(messages, tokenize=False)
                                inputs = tokenizer(input_text, return_tensors="pt")
                                
                                outputs = llm_model.generate(**inputs, max_new_tokens=50)
                                response_full = tokenizer.decode(outputs[0], skip_special_tokens=True)
                                
                                response_text = response_full
                                if "assistant\n" in response_full:
                                    response_text = response_full.split("assistant\n")[-1]
                                
                                print(f"LLM Response: {response_text}")
                                tux_say(response_text)
                            except Exception as e:
                                print(f"LLM Inference Error: {e}")
                                tux_say("I had an error processing that.")
                        else:
                            # Fallback if LLM failed to load
                            tux_say(f"I heard you say: {prompt}")
                            
            else:
                pass

    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Main Loop Error: {e}")
    finally:
        if tux_drv:
            tux_drv.Stop()
        print("Goodbye!")

if __name__ == '__main__':
    main()
