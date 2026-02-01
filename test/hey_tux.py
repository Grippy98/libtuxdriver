import sys
import os
import queue
import queue
import vosk
import json
import pyttsx3
import threading
import time
import ctypes

# Add include directory to path to find tux_driver.py
current_dir = os.path.dirname(os.path.abspath(__file__))
include_dir = os.path.join(current_dir, '../include')
sys.path.append(include_dir)

from tux_driver import *

# ALSA Error Suppression
try:
    ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p)
    def py_error_handler(filename, line, function, err, fmt):
        pass
    c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
    asound = ctypes.cdll.LoadLibrary('libasound.so')
    # Set error handler
    asound.snd_lib_error_set_handler(c_error_handler)
except Exception:
    pass

# Audio Config
SAMPLE_RATE = 16000
BLOCK_SIZE = 8000
q = queue.Queue()

# LLM Config
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    print("Loading SmolLM2-135M-Instruct...")
    checkpoint = "HuggingFaceTB/SmolLM2-135M-Instruct"
    tokenizer = AutoTokenizer.from_pretrained(checkpoint)
    llm_model = AutoModelForCausalLM.from_pretrained(checkpoint)
    print("LLM Loaded.")
except Exception as e:
    print(f"Warning: Could not load LLM: {e}")
    llm_model = None

# TTS Engine
engine = pyttsx3.init()
engine.setProperty('rate', 150)

# Tux Global State
tux_drv = None
mouth_thread = None
speaking = False

def mouth_animator():
    global speaking
    
    # Wait a bit for audio to start
    time.sleep(0.2)
    
    while speaking:
        # Open
        tux_drv.PerformCommand(0, "TUX_CMD:MOUTH:OPEN")
        time.sleep(0.2)
        if not speaking: break
        
        # Close
        tux_drv.PerformCommand(0, "TUX_CMD:MOUTH:CLOSE")
        time.sleep(0.2)
        
    # Ensure closed
    tux_drv.PerformCommand(0, "TUX_CMD:MOUTH:CLOSE")

def tux_say(text):
    global speaking, mouth_thread
    print(f"Tux says: {text}")
    
    speaking = True
    mouth_thread = threading.Thread(target=mouth_animator)
    mouth_thread.start()
    
    # engine.say blocks? No, engine.runAndWait() blocks.
    # But we need mouth animation to run in parallel.
    # pyttsx3 is tricky with threads. Let's try simple say+runAndWait
    
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"TTS Error: {e}")
        
    speaking = False
    mouth_thread.join()

def main():
    global tux_drv
    
    # 1. Setup Tux Driver
    lib_path = os.path.join(current_dir, '../unix/libtuxdriver.so')
    if not os.path.exists(lib_path):
        print("Error: libtuxdriver.so not found. Run 'make' in unix/ folder.")
        sys.exit(1)
        
    tux_drv = TuxDrv(lib_path)
    tux_drv.SetLogLevel(LOG_LEVEL_ERROR)
    
    print("Starting Tux Driver...")
    t = threading.Thread(target=tux_drv.Start)
    t.daemon = True
    t.start()
    
    # Wait for init
    time.sleep(4)
    tux_drv.ResetPositions()
    
    # 2. Setup Vosk
    if not os.path.exists("model"):
        print("Please download a Vosk model (e.g. vosk-model-small-en-us-0.15) and unpack as 'model' in this folder.")
        # Attempt Auto Download?
        try:
             from vosk import Model, KaldiRecognizer
             print("Loading Model...")
             # vosk.Model(lang="en-us") automagically downloads to ~/.cache/vosk
             model = Model(lang="en-us") 
        except Exception as e:
            print(f"Model load error: {e}")
            sys.exit(1)
    else:
        from vosk import Model, KaldiRecognizer
        model = Model("model")

    rec = KaldiRecognizer(model, SAMPLE_RATE)

    # 3. Microhone Loop
    print("\n-----------------------------")
    print(" LISTENING... Say 'Hey Tux'")
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
                        
                        # Extract prompt (everything after wake word)
                        # Find end of wake word in string
                        idx = lower_text.find(found_wake_word)
                        prompt = text[idx + len(found_wake_word):].strip()
                        
                        if not prompt:
                             prompt = "Hello" # Default interaction
                             
                        print(f"Prompting LLM: {prompt}")
                        tux_drv.PerformCommand(0, "TUX_CMD:EYES:BLINK")
                        
                        try:
                            # Run LLM generation
                            messages = [{"role": "user", "content": prompt}]
                            input_text = tokenizer.apply_chat_template(messages, tokenize=False)
                            inputs = tokenizer(input_text, return_tensors="pt")
                            
                            # Generate
                            outputs = llm_model.generate(**inputs, max_new_tokens=50) # Keep it short
                            response_full = tokenizer.decode(outputs[0], skip_special_tokens=True)
                            
                            # Extract just the assistant response
                            # The chat template decode usually includes the history. 
                            # SmolLM might output the whole thing.
                            # Basic string splitting to be safe:
                            response_text = response_full
                            if "assistant\n" in response_full:
                                response_text = response_full.split("assistant\n")[-1]
                            
                            print(f"LLM Response: {response_text}")
                            
                            tux_say(response_text)
                            
                        except Exception as e:
                            print(f"LLM Error: {e}")
                            tux_say("I am confused.")
                            
            else:
                # Partial result
                pass

    except KeyboardInterrupt:
        print("\nExiting...")
        tux_drv.Stop()

    except Exception as e:
        print(f"Error: {e}")
        tux_drv.Stop()

if __name__ == '__main__':
    main()
