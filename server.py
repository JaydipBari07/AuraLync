#!/usr/bin/env python3
"""
AuraLync Server - Stream audio from PC to phone via web browser
Uses binary WebSocket for low-latency audio streaming
"""

import asyncio
import socket
import soundcard as sc
import numpy as np
import threading
from queue import Queue, Full
from aiohttp import web
import socketio
import qrcode
import io
import warnings

warnings.filterwarnings('ignore', category=sc.SoundcardRuntimeWarning)

# Configuration
HOST = "0.0.0.0"
HTTP_PORT = 8080
SAMPLE_RATE = 44100
BLOCK_SIZE = 1024
CHANNELS = 2

class OptimizedAudioServer:
    def __init__(self):
        self.sio = socketio.AsyncServer(
            async_mode='aiohttp',
            cors_allowed_origins='*',
            ping_timeout=60,
            ping_interval=25,
            max_http_buffer_size=1000000
        )
        self.app = web.Application()
        self.sio.attach(self.app)
        
        self.clients = {}
        self.clients_lock = threading.Lock()
        self.is_streaming = False
        self.audio_thread = None
        self.mic = None
        
        self.setup_routes()
        self.setup_socketio()
        
    def setup_routes(self):
        self.app.router.add_get('/', self.index_handler)
        self.app.router.add_get('/qr', self.qr_handler)
        
    def setup_socketio(self):
        @self.sio.event
        async def connect(sid, environ):
            print(f'Client connected: {sid}')
            with self.clients_lock:
                self.clients[sid] = {'connected': True}
            await self.sio.emit('connection_status', {
                'status': 'connected',
                'sample_rate': SAMPLE_RATE,
                'block_size': BLOCK_SIZE,
                'channels': CHANNELS
            }, room=sid)
            
        @self.sio.event
        async def disconnect(sid):
            print(f'Client disconnected: {sid}')
            with self.clients_lock:
                if sid in self.clients:
                    del self.clients[sid]
                    
        @self.sio.event
        async def request_stream(sid, data):
            print(f'Stream requested by: {sid}')
            await self.sio.emit('stream_started', {}, room=sid)
    
    async def index_handler(self, request):
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AuraLync - Audio Streaming</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            color: white;
            padding: 20px;
        }
        
        .container { max-width: 600px; margin: 0 auto; width: 100%; }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
        }
        
        .badge {
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9rem;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        
        .qr-container {
            text-align: center;
            padding: 20px;
        }
        
        .qr-container img {
            max-width: 200px;
            background: white;
            padding: 10px;
            border-radius: 10px;
        }
        
        .status {
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 20px;
        }
        
        .status-dot {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-right: 10px;
            animation: pulse 2s infinite;
        }
        
        .status-dot.disconnected { background: #e74c3c; }
        .status-dot.connected { background: #2ecc71; }
        .status-dot.playing { background: #3498db; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .btn {
            width: 100%;
            padding: 18px;
            font-size: 1.2rem;
            font-weight: 600;
            border: none;
            border-radius: 15px;
            cursor: pointer;
            margin-top: 10px;
            color: white;
            transition: transform 0.2s;
        }
        
        .btn:active { transform: scale(0.98); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .btn-connect { background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%); }
        .btn-play { background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); }
        .btn-stop { background: linear-gradient(135deg, #95a5a6 0%, #7f8c8d 100%); }
        .btn-disconnect { background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); }
        
        .volume-control {
            margin-top: 20px;
        }
        
        .volume-label {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }
        
        .volume-value {
            font-weight: 700;
        }
        
        input[type="range"] {
            width: 100%;
            height: 8px;
            border-radius: 5px;
            background: rgba(255, 255, 255, 0.3);
            outline: none;
            -webkit-appearance: none;
        }
        
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: white;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }
        
        .stats {
            display: flex;
            justify-content: center;
            margin-top: 20px;
        }
        
        .stat-item {
            background: rgba(255, 255, 255, 0.1);
            padding: 20px 40px;
            border-radius: 10px;
            text-align: center;
            min-width: 200px;
        }
        
        .stat-label {
            font-size: 0.85rem;
            opacity: 0.8;
            margin-bottom: 5px;
        }
        
        .stat-value {
            font-size: 1.3rem;
            font-weight: 700;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AuraLync</h1>
            <div class="badge" id="bufferStatusBadge">Audio Streaming</div>
        </div>
        
        <div class="card qr-container">
            <div style="font-weight: 600; margin-bottom: 15px;">Scan to Connect</div>
            <img src="/qr" alt="QR Code">
        </div>
        
        <div class="card">
            <div class="status">
                <div class="status-dot disconnected" id="statusDot"></div>
                <span id="statusText">Disconnected</span>
            </div>
            
            <button class="btn btn-connect" id="connectBtn" onclick="connect()">
                Connect
            </button>
            
            <button class="btn btn-play" id="playBtn" onclick="startPlayback()" disabled style="display:none;">
                Start Playback
            </button>
            
            <button class="btn btn-stop" id="stopBtn" onclick="stopPlayback()" disabled style="display:none;">
                Stop
            </button>
            
            <button class="btn btn-disconnect" id="disconnectBtn" onclick="disconnect()" disabled style="display:none;">
                Disconnect
            </button>
        </div>
        
        <div class="card volume-control">
            <div class="volume-label">
                <span>Volume</span>
                <span class="volume-value" id="volumeValue">100%</span>
            </div>
            <input type="range" id="volumeSlider" min="0" max="200" value="100" oninput="updateVolume(this.value)">
        </div>
        
        <div class="card stats">
            <div class="stat-item">
                <div class="stat-label">Buffer</div>
                <div class="stat-value" id="bufferValue">--</div>
            </div>
        </div>
    </div>
    
    <script>
        let socket;
        let audioContext;
        let gainNode;
        let isConnected = false;
        let isPlaying = false;
        let sampleRate = 44100;
        let blockSize = 1024;
        let channels = 2;
        let scheduledTime = 0;
        let bufferSize = 0;
        
        // Buffer management - prevents audio delay from growing too large
        const TARGET_BUFFER = 0.15;    // target 150ms
        const MAX_BUFFER = 0.50;       // reset if exceeds 500ms
        const MIN_BUFFER = 0.05;       // minimum 50ms
        
        function updateStatus(status, text) {
            document.getElementById('statusDot').className = 'status-dot ' + status;
            document.getElementById('statusText').textContent = text;
        }
        
        function connect() {
            updateStatus('connected', 'Connecting...');
            
            socket = io({
                transports: ['websocket'],
                upgrade: false
            });
            
            socket.on('connect', () => {
                console.log('Connected to server');
                isConnected = true;
                updateStatus('connected', 'Connected');
                
                document.getElementById('connectBtn').style.display = 'none';
                document.getElementById('playBtn').style.display = 'block';
                document.getElementById('playBtn').disabled = false;
                document.getElementById('disconnectBtn').style.display = 'block';
                document.getElementById('disconnectBtn').disabled = false;
            });
            
            socket.on('connection_status', (data) => {
                sampleRate = data.sample_rate;
                blockSize = data.block_size;
                channels = data.channels;
            });
            
            socket.on('audio_data', (arrayBuffer) => {
                if (isPlaying) {
                    receiveAudioData(arrayBuffer);
                }
            });
            
            socket.on('disconnect', () => {
                handleDisconnection();
            });
        }
        
        async function startPlayback() {
            try {
                audioContext = new (window.AudioContext || window.webkitAudioContext)({
                    sampleRate: sampleRate,
                    latencyHint: 'interactive'
                });
                
                gainNode = audioContext.createGain();
                gainNode.connect(audioContext.destination);
                gainNode.gain.value = document.getElementById('volumeSlider').value / 100;
                
                scheduledTime = audioContext.currentTime;
                
                isPlaying = true;
                updateStatus('playing', 'Playing');
                
                document.getElementById('playBtn').style.display = 'none';
                document.getElementById('stopBtn').style.display = 'block';
                document.getElementById('stopBtn').disabled = false;
                
                socket.emit('request_stream', {});
                
                monitorStats();
                
            } catch (error) {
                console.error('Error:', error);
                alert('Error starting playback: ' + error.message);
            }
        }
        
        function stopPlayback() {
            isPlaying = false;
            
            if (audioContext) {
                audioContext.close();
                audioContext = null;
            }
            
            updateStatus('connected', 'Connected');
            
            document.getElementById('stopBtn').style.display = 'none';
            document.getElementById('playBtn').style.display = 'block';
            document.getElementById('playBtn').disabled = false;
            
            document.getElementById('bufferStatusBadge').textContent = 'Audio Streaming';
            document.getElementById('bufferStatusBadge').style.background = 'rgba(255,255,255,0.2)';
        }
        
        function disconnect() {
            if (isPlaying) {
                stopPlayback();
            }
            
            if (socket) {
                socket.disconnect();
            }
            
            handleDisconnection();
        }
        
        function handleDisconnection() {
            isConnected = false;
            isPlaying = false;
            
            if (audioContext) {
                audioContext.close();
                audioContext = null;
            }
            
            updateStatus('disconnected', 'Disconnected');
            
            document.getElementById('connectBtn').style.display = 'block';
            document.getElementById('playBtn').style.display = 'none';
            document.getElementById('stopBtn').style.display = 'none';
            document.getElementById('disconnectBtn').style.display = 'none';
            
            document.getElementById('bufferValue').textContent = '--';
            
            document.getElementById('bufferStatusBadge').textContent = 'Audio Streaming';
            document.getElementById('bufferStatusBadge').style.background = 'rgba(255,255,255,0.2)';
        }
        
        function receiveAudioData(arrayBuffer) {
            try {
                const audioData = new Float32Array(arrayBuffer);
                scheduleAudio(audioData);
            } catch (error) {
                console.error('Error processing audio:', error);
            }
        }
        
        function scheduleAudio(audioData) {
            if (!audioContext || !isPlaying) return;
            
            const currentTime = audioContext.currentTime;
            bufferSize = Math.max(0, scheduledTime - currentTime);
            
            // Reset if buffer gets too large (fixes pause/resume latency issue)
            if (bufferSize > MAX_BUFFER) {
                console.log(`Buffer overflow: ${bufferSize.toFixed(2)}s, resetting to ${TARGET_BUFFER}s`);
                scheduledTime = currentTime + TARGET_BUFFER;
                bufferSize = TARGET_BUFFER;
            }
            
            // Drop chunks if buffer is still high to let it drain
            if (bufferSize > TARGET_BUFFER * 1.5) {
                return;
            }
            
            if (scheduledTime < currentTime) {
                scheduledTime = currentTime + TARGET_BUFFER;
            }
            
            // Convert audio data to proper format
            const numFrames = audioData.length / channels;
            const audioBuffer = audioContext.createBuffer(channels, numFrames, sampleRate);
            
            for (let channel = 0; channel < channels; channel++) {
                const channelData = audioBuffer.getChannelData(channel);
                for (let i = 0; i < numFrames; i++) {
                    channelData[i] = audioData[i * channels + channel];
                }
            }
            
            // Schedule for playback
            const source = audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(gainNode);
            
            source.start(scheduledTime);
            scheduledTime += audioBuffer.duration;
            bufferSize = Math.max(0, scheduledTime - currentTime);
        }
        
        function updateVolume(value) {
            document.getElementById('volumeValue').textContent = value + '%';
            if (gainNode) {
                gainNode.gain.value = value / 100;
            }
        }
        
        function monitorStats() {
            if (!isPlaying) return;
            
            document.getElementById('bufferValue').textContent = bufferSize.toFixed(2) + 's';
            
            // Update buffer health indicator
            const badge = document.getElementById('bufferStatusBadge');
            if (bufferSize < MIN_BUFFER) {
                badge.textContent = 'Buffer Low';
                badge.style.background = 'rgba(231, 76, 60, 0.3)';
            } else if (bufferSize > MAX_BUFFER * 0.8) {
                badge.textContent = 'Buffer High';
                badge.style.background = 'rgba(230, 126, 34, 0.3)';
            } else {
                badge.textContent = 'Buffer OK';
                badge.style.background = 'rgba(46, 204, 113, 0.3)';
            }
            
            setTimeout(monitorStats, 100);
        }
    </script>
</body>
</html>
        """
        return web.Response(text=html, content_type='text/html')
    
    async def qr_handler(self, request):
        local_ip = self.get_local_ip()
        url = f"http://{local_ip}:{HTTP_PORT}"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return web.Response(body=img_byte_arr.read(), content_type='image/png')
    
    def capture_audio(self):
        # Capture system audio and send to connected clients
        try:
            print("Initializing audio capture...")
            default_speaker = sc.default_speaker()
            print(f"Using speaker: {default_speaker.name}")
            
            # Use loopback to capture system audio
            self.mic = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
            print(f"Microphone ready: {self.mic.name}")
            
            with self.mic.recorder(samplerate=SAMPLE_RATE) as recorder:
                while self.is_streaming:
                    try:
                        data = recorder.record(numframes=BLOCK_SIZE)
                        data_float32 = np.ascontiguousarray(data, dtype=np.float32)
                        data_bytes = data_float32.tobytes()
                        
                        with self.clients_lock:
                            client_sids = list(self.clients.keys())
                        
                        # Send audio to all connected clients
                        for sid in client_sids:
                            try:
                                asyncio.run_coroutine_threadsafe(
                                    self.sio.emit('audio_data', data_bytes, room=sid),
                                    self.loop
                                )
                            except Exception:
                                pass
                                
                    except Exception as e:
                        if self.is_streaming:
                            print(f"Audio capture error: {e}")
                        self.is_streaming = False
                        break
                        
        except Exception as e:
            print(f"Audio initialization error: {e}")
            print("\nNote: Enable 'Stereo Mix' in Windows sound settings if not working\n")
            self.is_streaming = False
    
    def start_streaming(self):
        if not self.is_streaming:
            self.is_streaming = True
            try:
                self.audio_thread = threading.Thread(target=self.capture_audio, daemon=True)
                self.audio_thread.start()
                print("Audio streaming started")
            except Exception as e:
                print(f"Failed to start audio: {e}")
                self.is_streaming = False
    
    async def start_server(self):
        print("Starting AuraLync Server...", flush=True)
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, HOST, HTTP_PORT)
        await site.start()
        
        local_ip = self.get_local_ip()
        server_url = f"http://{local_ip}:{HTTP_PORT}"
        
        print(f"""
========================================
AuraLync Server Running
========================================
URL: {server_url}

Open this URL on your phone browser
or scan the QR code below:
        """, flush=True)
        
        self.print_qr_code(server_url)
        
        self.start_streaming()
        
        self.loop = asyncio.get_event_loop()
        
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.is_streaming = False
    
    def print_qr_code(self, url):
        try:
            qr = qrcode.QRCode(version=1, box_size=1, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
            print()
        except Exception as e:
            print(f"QR code error: {e}", flush=True)
    
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"


def main():
    server = OptimizedAudioServer()
    asyncio.run(server.start_server())


if __name__ == "__main__":
    main()
