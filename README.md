# AuraLync
Allows you to stream system audio to unlimited listeners over your local network
---

## Quick Setup

### 1. Install Dependencies
```bash
pip install sounddevice numpy
```

### 2. Enable Stereo Mix (Windows)
To capture system audio:
1. Right-click speaker icon → **Sounds**
2. **Recording** tab → Right-click empty space → **Show Disabled Devices**
3. Right-click **Stereo Mix** → **Enable**
4. Click **OK**

### 3. Start Server
On the computer playing the video:
```bash
python audio_server.py
```
Note the IP address displayed (e.g., `192.168.1.100`)

### 4. Start Clients
On each listener's device:
```bash
python audio_client.py 192.168.1.100
```
Replace with your server's actual IP address.

### 5. Play Video
Play your video on the main computer. All clients will hear the audio through their headphones!

---

## Configuration

Edit these values at the top of `audio_server.py`:

```python
SAMPLE_RATE = 44100      # Audio quality (44100 = CD quality)
CHANNELS = 2             # 2 = Stereo, 1 = Mono
CHUNK_SIZE = 1024        # Smaller = lower latency, larger = more stable
PORT = 5555              # Change if this port is already in use
MAX_QUEUE_SIZE = 50      # Buffer size (larger = more stable, higher latency)

# Connection limits
MAX_CLIENTS = 50         # Maximum simultaneous clients (0 = unlimited)
LISTEN_BACKLOG = 10      # Pending connection queue size
```

### Client Connection Limits

**MAX_CLIENTS = 50** (default)
- Limits total simultaneous connections
- Set to `0` for unlimited (not recommended without testing)
- Clients beyond this limit are rejected with "Server full"

**LISTEN_BACKLOG = 10**
- Queue size for pending connections
- NOT the total client limit, just the waiting queue

### Configuration Presets

**For Smooth Audio (Default):**
```python
CHUNK_SIZE = 1024
MAX_QUEUE_SIZE = 50
MAX_CLIENTS = 50
```

**For Lower Latency (may have occasional noise):**
```python
CHUNK_SIZE = 512
MAX_QUEUE_SIZE = 20
MAX_CLIENTS = 30
```

**For Maximum Stability / Many Clients:**
```python
CHUNK_SIZE = 2048
MAX_QUEUE_SIZE = 100
MAX_CLIENTS = 100
```

### Practical Limitations

**Network Bandwidth per client:**
- Data Rate = Sample Rate * Channels * Bytes per Sample
- Data rate: ~353 KB/s per client (44100 Hz stereo)
- 10 clients = 3.5 MB/s
- 20 clients = 7 MB/s
- 50 clients = 17.6 MB/s

---

## How It Works - Technical Details

### Architecture Overview

<img width="441" height="461" alt="AuraLync" src="https://github.com/user-attachments/assets/745ceea4-0929-424e-9f9a-1702dec15161" />

### Python Libraries Used

#### 1. **sounddevice** - Audio I/O
- **Purpose**: Captures system audio (server) and plays audio (client)
- **Backend**: Uses PortAudio library
- **Key Features**:
  - Cross-platform audio I/O
  - Low-latency streaming
  - Callback-based processing


#### 2. **numpy** - Audio Data Processing
- **Purpose**: Handle audio as numeric arrays
- **Why**: Audio data is float32 arrays of samples
- **Operations**:
  - Convert bytes to numpy arrays: `np.frombuffer(data, dtype=np.float32)`
  - Reshape for channels: `array.reshape(-1, CHANNELS)`
  - Convert to bytes: `array.tobytes()`

**Audio Format:**
```python
# Each audio chunk is a 2D numpy array:
# Shape: (1024, 2) for stereo at CHUNK_SIZE=1024
# Values: float32 in range [-1.0, 1.0]
# Size: 1024 samples × 2 channels × 4 bytes = 8192 bytes
```

#### 3. **socket** - Network Communication
- **Purpose**: TCP streaming from server to clients
- **Protocol**: TCP for reliable delivery
- **Port**: 5555 (configurable)

#### 4. **threading** - Concurrent Operations
- **Purpose**: Handle multiple tasks simultaneously
- **Threads Used**:
  - Audio capture thread (sounddevice callback)
  - Broadcast thread (send to all clients)
  - Accept clients thread (handle new connections)
  - Audio playback thread (sounddevice callback)

#### 5. **queue** - Thread-Safe Buffer
- **Purpose**: Pass audio data between threads safely
- **Type**: `queue.Queue(maxsize=50)`
- **Why**: Prevents race conditions, provides buffering

### Data Flow

#### Server Side:
```
1. sounddevice captures audio → audio_callback()
2. audio_callback() → puts data in queue
3. broadcast_thread() → gets data from queue
4. broadcast_thread() → sends to all clients via socket
```

#### Client Side:
```
1. receive_thread() → receives data from socket
2. receive_thread() → puts data in queue
3. audio_callback() → gets data from queue
4. sounddevice plays audio through headphones
```

### Packet Structure

Each audio packet contains:
```
┌──────────────┬────────────────────────┐
│ 4 bytes      │ N bytes                │
│ Size (int)   │ Audio Data (float32)   │
└──────────────┴────────────────────────┘
```

### Timing & Latency

**Chunk Duration:**
- At 44100 Hz with CHUNK_SIZE=1024: 
  - Duration = 1024 / 44100 ≈ 23ms per chunk

**Latency Components:**
1. Audio capture: ~23ms (one chunk)
2. Server queue: ~23ms × 50 chunks = ~1.15s
3. Network transmission: ~10-50ms (LAN)
4. Client queue: ~23ms × 100 chunks = ~2.3s
5. Audio playback: ~23ms (one chunk)

**Total: ~1-2 seconds**

**!! Watch together. Listen apart. Bother no one. !!**
