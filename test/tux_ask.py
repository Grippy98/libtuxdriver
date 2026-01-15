
import ctypes
import time
import os
import sys
import subprocess
from gtts import gTTS
import threading
import google.generativeai as genai

# Load library
import random
import speech_recognition as sr

# Load library
script_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(script_dir, "../unix/libtuxdriver.so")
lib = ctypes.CDLL(lib_path)

# Callback types
STATUS_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_char_p)

# Global for recognizer
r = sr.Recognizer()
mic = None  # Initialized in setup()

stop_listening_bg = None  # Function to stop background listener

# Lock for robot commands
cmd_lock = threading.Lock()

# Global flag for mouth thread
speaking = False
mouth_thread = None
# Global flag for blink thread
blinking = True
blink_thread_handle = None

head_button_pressed = False
wakeword_detected = False

# ALSA Error Suppression
from contextlib import contextmanager

ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p)

def py_error_handler(filename, line, function, err, fmt):
    pass

c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

@contextmanager
def no_alsa_error():
    asound = None
    try:
        asound = ctypes.cdll.LoadLibrary('libasound.so')
        asound.snd_lib_error_set_handler(c_error_handler)
        yield
    except Exception:
        yield
    finally:
        if asound:
            asound.snd_lib_error_set_handler(None)

def on_status(status):
    global head_button_pressed
    try:
        if status:
            status_str = status.decode('utf-8', errors='ignore')
            # Look for head_button change
            if "head_button" in status_str:
                # Format might be "head_button:True" or similar?
                # The callback receives ALL changed statuses.
                if "head_button:True" in status_str:
                    head_button_pressed = True
    except:
        pass

def wakeword_callback(recognizer, audio):
    global wakeword_detected
    try:
        # Check for "hey tux" or "tux"
        # Adjust threshold sensitivity as needed
        keywords = [("hey tux", 1e-20), ("tux", 1e-20)]
        print(".", end="", flush=True) # visual heartbeat
        
        # Recognize using PocketSphinx (offline)
        # Note: accurate keyword spotting requires a little tuning
        detected = recognizer.recognize_sphinx(audio, keyword_entries=keywords)
        
        if "tux" in detected.lower():
            print(f"\nWake word detected: '{detected}'")
            wakeword_detected = True
            
    except sr.UnknownValueError:
        pass # No speech or no keyword matches
    except sr.RequestError as e:
        print(f"Sphinx error: {e}")
    except Exception as e:
        pass # Ignore other errors in background

def start_wakeword_listener():
    global stop_listening_bg
    if stop_listening_bg:
        return # Already running
        
    print("Starting wake word listener (Say 'Hey Tux')...")
    try:
        with no_alsa_error():
            # Adjust energy threshold for ambient noise
            with mic as source:
                r.adjust_for_ambient_noise(source)
            
            # phrase_time_limit=2.0 helps keep audio chunks small for quick wake word checks
            stop_listening_bg = r.listen_in_background(mic, wakeword_callback, phrase_time_limit=2.0)
    except Exception as e:
        print(f"Warning: Failed to start wake word listener. Microphone issue? Error: {e}")
        stop_listening_bg = None

def stop_wakeword_listener():
    global stop_listening_bg
    if stop_listening_bg:
        stop_listening_bg(wait_for_stop=False)
        stop_listening_bg = None
        print("Stopped background listener.")

# ... (existing functions) ...

def listen_for_speech():
    print("Listening for speech...")
    with cmd_lock:
        # Visual cue: Eyes blink rapidly? Or just open wide.
        lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:EYES:OPEN")
        # Maybe stop blinking momentarily?
    
    try:
        with no_alsa_error():
            with mic as source:
                r.adjust_for_ambient_noise(source)
                print("Speak now!")
                # Play a beep? No beep command known yet.
                audio = r.listen(source, timeout=5.0)
        
        print("Recognizing...")
        text = r.recognize_google(audio)
        print(f"Heard: {text}")
        return text
    except sr.WaitTimeoutError:
        print("No speech detected.")
        return None
    except sr.UnknownValueError:
        print("Could not understand audio.")
        return None
    except sr.RequestError as e:
        print(f"Could not request results; {e}")
        return None
    except Exception as e:
        print(f"Error in speech recognition: {e}")
        return None


status_cb = STATUS_CALLBACK(on_status)

def mouth_animator():
    global speaking
    
    # Wait a bit for audio to potentially start
    time.sleep(0.5)
    
    while speaking:
        with cmd_lock:
            # Open
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:MOUTH:OPEN")
        time.sleep(0.2)
        if not speaking: break
        
        with cmd_lock:
            # Close
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:MOUTH:CLOSE")
        time.sleep(0.2)
        
    # Ensure closed
    with cmd_lock:
        lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:MOUTH:CLOSE")

def blink_animator():
    global blinking
    print("Blink thread started.")
    
    while blinking:
        # Sleep random interval
        time.sleep(random.uniform(2.0, 8.0))
        if not blinking: break
        
        # Blink
        with cmd_lock:
            # Only blink if eyes are currently open (simple heuristic). 
            # We could read status, but locking protects us mostly.
            # Just do a blink sequence.
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:EYES:CLOSE")
        
        time.sleep(0.2)
        
        with cmd_lock:
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:EYES:OPEN")


def speak(audio_file):
    global speaking, mouth_thread
    
    if not os.path.exists(audio_file):
        print(f"Error: Audio file {audio_file} not found!")
        return

    print("Playing audio and animating mouth...")
    # Ensure eyes are open when speaking starts
    with cmd_lock:
        lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:EYES:OPEN")
        
    speaking = True
    mouth_thread = threading.Thread(target=mouth_animator)
    mouth_thread.start()
    
    # Play audio (blocking)
    try:
        subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", audio_file], check=True)
    except Exception as e:
        print(f"Error playing audio: {e}")
    
    speaking = False
    mouth_thread.join()
    print("Done speaking.")

def generate_audio(text):
    print(f"Generating TTS for: '{text}'")
    try:
        # Use espeak for male voice
        # -v en-us+m3 gives a male American voice, -s 150 sets speed
        outfile = "output.wav"
        subprocess.run(["espeak", "-v", "en-us+m3", "-s", "150", "-w", outfile, text], check=True)
        return outfile
    except Exception as e:
        print(f"Failed to generate TTS: {e}")
        return None

def perform_animation(tag):
    print(f"Performing animation for: {tag}")
    tag = tag.upper()
    
    with cmd_lock:
        if tag == "[HAPPY]":
            # Flippers UP, wait, DOWN. Eyes OPEN.
            print("Cmd: HAPPY")
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:FLIPPERS:UP")
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:EYES:OPEN")
            time.sleep(1.0)
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:FLIPPERS:DOWN")
            
        elif tag == "[SAD]":
            # Flippers DOWN. Eyes CLOSE.
            print("Cmd: SAD")
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:FLIPPERS:DOWN")
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:EYES:CLOSE")
            
        elif tag == "[EXCITED]":
            # Spin LEFT, Spin RIGHT. Flippers UP.
            print("Cmd: EXCITED")
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:FLIPPERS:UP")
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:SPINNING:LEFT_ON")
            time.sleep(0.5)
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:SPINNING:RIGHT_ON")
            time.sleep(0.5)
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:SPINNING:OFF")

        elif tag == "[WAVE]":
            # Wave flippers
            print("Cmd: WAVE")
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:FLIPPERS:UP")
            time.sleep(0.3)
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:FLIPPERS:DOWN")
            time.sleep(0.3)
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:FLIPPERS:UP")
            time.sleep(0.3)
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:FLIPPERS:DOWN")

        elif tag == "[DANCE]":
            # Spin and flap
            print("Cmd: DANCE")
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:SPINNING:LEFT_ON")
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:FLIPPERS:UP")
            time.sleep(0.5)
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:FLIPPERS:DOWN")
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:SPINNING:RIGHT_ON")
            time.sleep(0.5)
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:SPINNING:OFF")
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:EYES:BLINK")

        elif tag == "[ANGRY]":
             # Eyes CLOSE, Spin abruptly
            print("Cmd: ANGRY")
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:EYES:CLOSE")
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:SPINNING:LEFT_ON")
            time.sleep(0.2)
            lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:SPINNING:OFF")


def ask_gemini(prompt):
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        try:
            # Look for api_key.txt in the same directory as the script
            key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_key.txt")
            if os.path.exists(key_file):
                with open(key_file, "r") as f:
                    api_key = f.read().strip()
        except Exception as e:
            print(f"Error reading api_key.txt: {e}")

    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set and test/api_key.txt found.")
        return None, "I need an API key to think."
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        system_instruction = "You are Tux, a Linux penguin robot. You control your physical body with tags. " \
                             "ALWAYS start your response with ONE of these tags found in brackets: " \
                             "[HAPPY], [SAD], [EXCITED], [WAVE], [DANCE], [ANGRY], or [NEUTRAL] if no emotion fits. " \
                             "The tag must be the very first thing. Example: '[HAPPY] I love Linux!'"
        
        full_prompt = f"{system_instruction}\n\nUser: {prompt}\nTux:"

        print("Asking Gemini...")
        response = model.generate_content(full_prompt)
        text = response.text
        
        # Parse tag
        tag = "[NEUTRAL]"
        clean_text = text
        
        if text.startswith("["):
            end_idx = text.find("]")
            if end_idx != -1:
                tag = text[:end_idx+1]
                clean_text = text[end_idx+1:].strip()
        
        # Cleanup
        clean_text = clean_text.replace("*", "").replace("#", "")
        return tag, clean_text
        
    except Exception as e:
        print(f"Error querying Gemini: {e}")
        return "[SAD]", "My brain hurts."

def setup():
    global blink_thread_handle, mic
    print("Starting TuxDriver in background thread...")
    lib.TuxDrv_SetLogLevel(1) # ERROR only
    lib.TuxDrv_SetLogTarget(0) # SHELL
    lib.TuxDrv_SetStatusCallback(status_cb)
    
    # Run Start in a thread because it blocks
    t = threading.Thread(target=lib.TuxDrv_Start)
    t.daemon = True
    t.start()
    
    print("Initializing Microphone...")
    mic = None
    with no_alsa_error():
        try:
            # Try User Preferred Index (12 - PulseAudio) first
            # Note: Index availability can change (e.g. running as root vs user)
            print("Attempting to connect to PulseAudio (Index 12)...")
            mic = sr.Microphone(device_index=12)
        except (AssertionError, OSError):
            print("Index 12 not found. Falling back to default microphone...")
            try:
                mic = sr.Microphone()
            except Exception as e:
                print(f"Error initializing default microphone: {e}")
                mic = None

    if mic:
        print("Microphone initialized.")
    else:
        print("WARNING: No microphone found. Voice features will be disabled.")
    
    print("Waiting for init...")
    time.sleep(4)
    # Reset state
    with cmd_lock:
        lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:EYES:OPEN")
        lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:FLIPPERS:DOWN")
        
    # Start blink thread
    blink_thread_handle = threading.Thread(target=blink_animator)
    blink_thread_handle.daemon = True
    blink_thread_handle.start()

def cleanup():
    global blinking
    blinking = False
    
    if blink_thread_handle:
        blink_thread_handle.join(timeout=1.0)
        
    lib.TuxDrv_Stop()
    if os.path.exists("output.mp3"):
        os.remove("output.mp3")
    if os.path.exists("output.wav"):
        os.remove("output.wav")

if __name__ == "__main__":
    setup()
    try:
        print("Tux is listening! Type 'exit', press HEAD BUTTON, or say 'hey tux'.")
        
        # Start wake word listener
        start_wakeword_listener()
        
        # Need to set stdin to non-blocking or use select
        import select
        
        while True:
            # Check for keyboard input
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                line = sys.stdin.readline()
                if line:
                    prompt = line.strip()
                    if prompt.lower() in ['exit', 'quit']:
                        break
                    
                    if prompt:
                        stop_wakeword_listener() # Pause listening while processing
                        
                        tag, response_text = ask_gemini(prompt)
                        print(f"Tux ({tag}) > {response_text}")
                        
                        anim_thread = threading.Thread(target=perform_animation, args=(tag,))
                        anim_thread.start()
                        
                        audio_file = generate_audio(response_text)
                        if audio_file:
                            speak(audio_file)
                            if os.path.exists(audio_file):
                                os.remove(audio_file)
                        anim_thread.join()
                        
                        start_wakeword_listener() # Resume listening

            # Check triggers: Button OR Wake Word
            if head_button_pressed or wakeword_detected:
                if wakeword_detected:
                    print("\nWake word triggered!")
                    wakeword_detected = False
                if head_button_pressed:
                    print("\nButton triggered!")
                    head_button_pressed = False
                
                stop_wakeword_listener() # Stop background listener to free mic
                
                # Trigger listening
                prompt = listen_for_speech()
                if prompt:
                    tag, response_text = ask_gemini(prompt)
                    print(f"Tux ({tag}) > {response_text}")
                    
                    anim_thread = threading.Thread(target=perform_animation, args=(tag,))
                    anim_thread.start()
                    
                    audio_file = generate_audio(response_text)
                    if audio_file:
                        speak(audio_file)
                        if os.path.exists(audio_file):
                            os.remove(audio_file)
                    anim_thread.join()
                
                start_wakeword_listener() # Resume listening
            
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nExiting...")
                
    finally:
        stop_wakeword_listener()
        cleanup()

