libtuxdriver is a shared library to control Tuxdroid.

For all information about Tuxdroid, please visit:

  http://tuxdroid-community.org/
  http://www.tux-droid.eu/

# tuxdriver

Userspace driver for the Tux Droid robot.

## Build

### System Dependencies
- **Fedora**: `sudo dnf install python3-devel portaudio-devel alsa-lib-devel espeak-ng gcc-c++`
- **Debian/Ubuntu**: `sudo apt install python3-dev portaudio19-dev libasound2-dev espeak-ng gcc`

### Python Dependencies
Using a virtual environment is recommended:
```bash
python3 -m venv test/venv
source test/venv/bin/activate
pip install vosk pyttsx3 pyaudio
```

### Installation
1. Compile the C library:
   ```bash
   cd unix
   make
   ```
## Run

To test the driver:

    export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:`pwd`/unix
    ./test/tux_test

### LLM Chat Mode

A new interactive script allows you to chat with Tux using the Gemini LLM!

**Features:**
- **Voice Response**: Tux speaks invalid responses using a male voice (`espeak`).
- **Mouth Animation**: Tux moves his mouth in sync with speech.
- **Context-Aware Animations**: Tux performs physical actions based on his emotions!
    - `[HAPPY]`: Flaps flippers joyfully.
    - `[SAD]`: Droops head and flippers.
    - `[EXCITED]`: Spins around excitedly.
    - `[DANCE]`: Does a little dance!
    - `[WAVE]`: Waves hello.
    - `[ANGRY]`: Squints and spins abruptly.
- **Lifelike Blinking**: Tux blinks his eyes periodically while idle.

**Requirements:**
- Python 3
- `espeak` (`sudo apt install espeak`)
- `portaudio19-dev` (`sudo apt install portaudio19-dev`) for microphone access
- `google-generativeai` (install via `pip install google-generativeai`)
- `SpeechRecognition`, `pyaudio`
- A Google Gemini API Key

**Usage:**
1.  Set your API key in `test/api_key.txt` or the `GEMINI_API_KEY` environment variable.
2.  Run the script:
    ```bash
    ./test/venv/bin/python3 test/tux_ask.py
    ```
3.  Type your message and press Enter.


### Voice Control
You can also talk to Tux!
1.  **Press and Release** the button on Tux's Head.
2.  Tux will open his eyes wide and print "Listening...".
3.  Speak your question clearly.
4.  Tux will process your speech and reply!
5.  **Hands-Free**: Just say **"Hey Tux"** (or "Tux") to wake him up!

## Linux Setup (Permissions)

To access the Tux Droid hardware without root privileges, you must configure udev rules.

1. Create a file named `/etc/udev/rules.d/99-tux.rules`:
   ```bash
   sudo nano /etc/udev/rules.d/99-tux.rules
   ```

2. Add the following content:
   ```bash
   SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="ff07", MODE="0666"
   ```

3. Reload rules and reconnect the device:
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```
