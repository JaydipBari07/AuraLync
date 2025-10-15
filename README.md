# AuraLync 🎧
Stream system audio to multiple listeners over your local network with a modern GUI interface.

---

## 🚀 Quick Setup

### Option 1: Use Pre-built Executables (Recommended)
**If you don't have Python installed or facing setup issues:**
1. Download the latest release executables
2. Run `server.exe` on the host computer
3. Run `client.exe` on listener devices
4. No installation needed!

### Option 2: Run from Source

#### 1. Install Dependencies
```bash
pip install soundcard sounddevice numpy tkinter
```

#### 2. Start Server
On the computer that will stream audio:
```bash
python server.py
```
- Click **"Start Server"**
- Note the IP address displayed (e.g., `192.168.1.100`)

#### 3. Start Clients
On each listener's device:
```bash
python client.py
```
- Enter the **server IP address** and **port** (default: 50007)
- Select your **audio output device**
- Click **"Connect"**
- Adjust **volume boost** slider as needed (1x to 10x)

#### 4. Play Audio
Play anything on the server computer - all connected clients will hear it in real-time!

---

## ✨ Features

- **Multi-Client Support** - Stream to unlimited listeners simultaneously
- **Modern GUI Interface** - Easy-to-use controls for both server and client
- **Volume Control** - Individual volume boost (1x-10x) on each client
- **Device Selection** - Choose your preferred audio output device
- **Real-time Status** - Monitor connections and streaming status
- **Low Latency** - Optimized queue-based broadcasting for smooth playback
- **Auto-discovery** - Server displays its IP address automatically

---

## 🏗️ Architecture Overview

### High-Level Design

```
┌─────────────────────┐
│   Server Computer   │
│  ┌───────────────┐  │
│  │  System Audio │  │ ← Captures all audio (music, video, games)
│  └───────┬───────┘  │
│          │          │
│  ┌───────▼───────┐  │
│  │ Audio Capture │  │ ← soundcard library records audio
│  │    Thread     │  │
│  └───────┬───────┘  │
│          │          │
│  ┌───────▼───────┐  │
│  │  Broadcast to │  │ ← Separate queue per client
│  │  All Clients  │  │
│  └───────┬───────┘  │
└──────────┼──────────┘
           │
    ┌──────┴──────┐
    │   Network   │ TCP Sockets (Port 50007)
    └──────┬──────┘
           │
    ┌──────┴───────────────────┐
    │                          │
┌───▼──────┐            ┌──────▼───┐
│ Client 1 │            │ Client N │
│  ┌────┐  │            │  ┌────┐  │
│  │RCV │  │   ...      │  │RCV │  │ ← Receiver Thread
│  └─┬──┘  │            │  └─┬──┘  │
│  ┌─▼──┐  │            │  ┌─▼──┐  │
│  │ Q  │  │            │  │ Q  │  │ ← Audio Queue Buffer
│  └─┬──┘  │            │  └─┬──┘  │
│  ┌─▼──┐  │            │  ┌─▼──┐  │
│  │Vol │  │            │  │Vol │  │ ← Volume Boost
│  └─┬──┘  │            │  └─┬──┘  │
│  ┌─▼──┐  │            │  ┌─▼──┐  │
│  │OUT │  │            │  │OUT │  │ ← Audio Playback
│  └────┘  │            │  └────┘  │
└──────────┘            └──────────┘
```

### Key Components

**Server (`server.py`):**
- **Audio Capture Thread**: Continuously records system audio using loopback device
- **Client Handler Threads**: One thread per connected client for independent streaming
- **Queue-based Broadcasting**: Each client has dedicated queue to prevent interference
- **Connection Manager**: Accepts new clients and manages disconnections

**Client (`client.py`):**
- **Receiver Thread**: Receives audio packets from server over TCP
- **Audio Queue**: Buffers incoming audio for smooth playback (20 packets)
- **Callback Playback**: Audio callback pulls from queue for glitch-free output
- **Volume Processing**: Real-time gain adjustment with clipping protection

### Data Flow

1. **Server captures** system audio → 1024 samples at 44100 Hz (23ms chunks)
2. **Audio data** converted to float32 bytes → ~8KB per packet
3. **Broadcast** to all client queues simultaneously (non-blocking)
4. **Network transmission** via TCP sockets
5. **Client receives** packets → stores in queue
6. **Audio callback** pulls from queue → applies volume → plays audio

### Thread Safety

- **Locks**: Protect shared client list during add/remove operations
- **Queues**: Thread-safe communication between receiver and playback
- **Non-blocking puts**: Drop packets if client queue full (prevents slowdown)

---

## ⚙️ Configuration

Edit these values in `server.py` and `client.py`:

```python
PORT = 50007          # Network port (change if blocked)
SAMPLE_RATE = 44100   # Audio quality (44.1 kHz CD quality)
BLOCK_SIZE = 1024     # Samples per chunk (affects latency)
```

### Audio Quality vs Latency

- **Lower BLOCK_SIZE** (512): Lower latency (~12ms) but more CPU usage
- **Higher BLOCK_SIZE** (2048): Higher latency (~46ms) but more stable

---

## 🔧 Troubleshooting

**Server not capturing audio?**
- Ensure loopback/stereo mix is enabled in system audio settings

**Client can't connect?**
- Check firewall allows traffic on port 50007
- Verify server and client are on the same network

**Audio too quiet?**
- Use the volume boost slider on client (try 3x-5x)

**Audio choppy/glitchy?**
- Check network connection quality
- Increase BLOCK_SIZE for more buffering

---

**!! Watch together. Listen apart. Bother no one. !!**
