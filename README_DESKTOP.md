# Project Mythos Desktop Launcher

Mythos can run like a Windows desktop assistant while keeping the existing Streamlit app as the UI/backend.

## 1. Setup

Install the existing app dependencies:

```powershell
pip install -r requirements.txt
```

Create a local `.env` file in this project folder:

```env
OPENAI_API_KEY=your_openai_key_here
MYTHOS_HOST=localhost
MYTHOS_PORT=8501
```

`OPENAI_API_KEY` is needed for Mythos voice mode, speech-to-text, text-to-speech, and AI agents.

## 2. Start Mythos

Double-click:

```text
start_mythos.bat
```

Or run:

```powershell
python desktop_launcher.py --start
```

The launcher will:

- load `.env`
- check whether Mythos is already running
- start Streamlit if needed
- open Mythos at `http://MYTHOS_HOST:MYTHOS_PORT`

## 3. Stop Mythos

Double-click:

```text
stop_mythos.bat
```

Or run:

```powershell
python desktop_launcher.py --stop
```

Logs are written to:

```text
.mythos_runtime\streamlit.log
```

## 4. Restart Mythos

```powershell
python desktop_launcher.py --restart
```

## 5. Optional Desktop Window

By default, Mythos opens in your browser. If you want a native-looking desktop window, install `pywebview`:

```powershell
pip install pywebview
python desktop_launcher.py --start --window
```

If `pywebview` has issues, Mythos automatically falls back to your browser.

## 6. Futuristic Native Shell

Project Mythos also includes a premium PyQt6 desktop shell:

```powershell
pip install PyQt6
python desktop_launcher.py --start --native
```

This opens a dark, cinematic AI command center with:

- animated Mythos core
- matte black background
- blue-cyan and purple glow accents
- floating quick commands
- glass side panels
- desktop assistant feel

The Streamlit app still runs in the background for the existing backend/UI. This native shell is currently a visual command center shell; full two-way agent integration can be added next.

The native shell's `VOICE` button opens the working Mythos AI Command Center in the browser. Use that page for real microphone capture, speech-to-text, and audio playback.

## 7. Optional System Tray

Install optional tray dependencies:

```powershell
pip install pystray pillow
python desktop_launcher.py --tray
```

Tray menu:

- Open Mythos
- Restart Mythos
- Stop Mythos
- Exit

If tray support is unavailable, the launcher falls back to opening Mythos normally.

## 8. Windows Startup

Mythos does not auto-start by default.

To enable startup manually:

1. Press `Win + R`.
2. Run:

   ```text
   shell:startup
   ```

3. Create a shortcut to `start_mythos.bat` in that folder.

To disable startup, delete that shortcut.

## 9. Voice Mode

Voice mode still runs inside the Mythos Streamlit UI.

Requirements:

- `OPENAI_API_KEY` set in `.env`
- browser microphone permission allowed
- a supported browser

If microphone capture fails, Mythos falls back to text input.

## 10. Limitations

- This is a lightweight desktop wrapper, not a fully native Windows app yet.
- The browser or `pywebview` window still renders the Streamlit UI.
- The PyQt6 native shell is a futuristic desktop interface shell and does not yet replace every Streamlit workflow.
- Native-shell voice is not directly wired yet; real voice mode runs in the Streamlit AI Command Center opened by the `VOICE` button.
- Microphone permission is controlled by the browser/webview.
- The launcher tracks the Streamlit process it starts. If you start Streamlit manually on the same port, the launcher will open it instead of starting a duplicate.
