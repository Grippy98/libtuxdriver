import ctypes
import time
import os
import sys
import subprocess
from gtts import gTTS
import threading

# Load library
lib = ctypes.CDLL("../unix/libtuxdriver.so")

# Callback types
STATUS_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_char_p)

# Global flag for mouth thread
speaking = False
mouth_thread = None

def on_status(status):
    pass

status_cb = STATUS_CALLBACK(on_status)

def mouth_animator():
    global speaking
    
    # Wait a bit for audio to potentially start
    time.sleep(0.5)
    
    while speaking:
        # Open
        lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:MOUTH:OPEN")
        time.sleep(0.2)
        if not speaking: break
        
        # Close
        lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:MOUTH:CLOSE")
        time.sleep(0.2)
        
    # Ensure closed
    lib.TuxDrv_PerformCommand(ctypes.c_double(0.0), b"TUX_CMD:MOUTH:CLOSE")

def speak(audio_file):
    global speaking, mouth_thread
    
    if not os.path.exists(audio_file):
        print(f"Error: Audio file {audio_file} not found!")
        return

    print("Playing audio and animating mouth...")
    speaking = True
    mouth_thread = threading.Thread(target=mouth_animator)
    mouth_thread.start()
    
    # Play audio (blocking)
    # Try ffplay first, then aplay if wav (but this is mp3)
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
        tts = gTTS(text, lang='en')
        tts.save("output.mp3")
        print("TTS generated successfully: output.mp3")
        return "output.mp3"
    except Exception as e:
        print(f"Failed to generate TTS: {e}")
        return None

def setup():
    print("Starting TuxDriver in background thread...")
    lib.TuxDrv_SetLogLevel(1) # ERROR only
    lib.TuxDrv_SetLogTarget(0) # SHELL
    lib.TuxDrv_SetStatusCallback(status_cb)
    
    # Run Start in a thread because it blocks
    t = threading.Thread(target=lib.TuxDrv_Start)
    t.daemon = True
    t.start()
    
    print("Waiting for init...")
    time.sleep(4)

def cleanup():
    lib.TuxDrv_Stop()
    if os.path.exists("output.mp3"):
        os.remove("output.mp3")
if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = "Hello! I am Tux. I can speak and move my mouth."
        
    audio_file = generate_audio(text)
    
    if audio_file:
        setup()
        try:
            speak(audio_file)
        finally:
            cleanup()
