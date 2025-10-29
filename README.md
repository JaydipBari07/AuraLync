# AuraLync

Stream audio from your PC to any device with a web browser. No app installation needed.

---

## Quick Start

### Option 1: Use Executable (Easiest)

1. [⬇️ Download serverv2.0.exe](https://github.com/jaydipbari/AuraLync/blob/v2.0/executables/v2.0/serverv2.0.exe)
2. Run the executable
3. Scan the QR code with your phone
4. Click "Connect" and "Start Playback"

**That's it!** Your PC audio now plays on your phone.

---

### Option 2: Run from Source

#### 1. Install Requirements

```bash
pip install -r requirements.txt
```

#### 2. Run the Server

```bash
python server.py
```

#### 3. Connect from Phone

- Scan the QR code shown in terminal
- Or open the URL in your phone's browser
- Click "Connect" → "Start Playback"

---

## Features

- **Browser-based** - Works on any device (phone, tablet, laptop)
- **No app needed** - Just open in web browser
- **QR Code** - Instant connection
- **Volume control** - Adjust from 0-200%
- **Auto buffer management** - Prevents audio delay buildup
- **Multiple clients** - Connect unlimited devices

---

## System Requirements

**PC (Server):**
- Windows 10/11
- Python 3.8+ (if running from source)
- Stereo Mix enabled (for audio capture)

**Client:**
- Any device with web browser
- Same WiFi network as PC

---


## Troubleshooting

**No audio being captured?**
- Enable "Stereo Mix" in Windows sound settings
- Right-click speaker icon → Sounds → Recording → Enable Stereo Mix

**Connection issues?**
- Make sure PC and phone are on same WiFi
- Check firewall isn't blocking port 8080

**Audio lag increasing?**
- The app auto-resets buffer when it exceeds 500ms
- If issue persists, restart the server

---

## How It Works

1. Server captures system audio using loopback
2. Streams audio as binary data via WebSocket
3. Browser receives and plays audio in real-time
4. Buffer management prevents delay accumulation

**Network:** Uses Socket.IO for reliable communication  
**Audio Format:** 44.1kHz, 2 channels, Float32  
**Latency:** ~150ms (configurable)

---

## Configuration

Edit these in `server.py`:

```python
HTTP_PORT = 8080       # Change if port is in use
SAMPLE_RATE = 44100    # Audio quality
BLOCK_SIZE = 1024      # Chunk size (affects latency)
```

Client buffer settings (in HTML):

```javascript
TARGET_BUFFER = 0.15   // 150ms target
MAX_BUFFER = 0.50      // Reset at 500ms
MIN_BUFFER = 0.05      // Minimum 50ms
```

**!! Watch together. Listen apart. Bother no one. !!**
