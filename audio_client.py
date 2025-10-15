"""
Audio Streaming Client
Connects to the audio server and plays received audio through local speakers/headphones.

Requirements: pip install sounddevice numpy

Usage: python audio_client.py <server_ip>
Example: python audio_client.py 192.168.1.100
"""

import socket
import sounddevice as sd
import numpy as np
import json
import sys
import queue
import threading

# Configuration (will be updated from server)
SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK_SIZE = 1024
BUFFER_SIZE = 4096

audio_queue = queue.Queue(maxsize=100)

def audio_callback(outdata, frames, time_info, status):
    """Called when audio needs to be played"""
    if status:
        print(f"Audio status: {status}")
    
    try:
        data = audio_queue.get_nowait()
        outdata[:] = data
    except queue.Empty:
        # If no data available, output silence
        outdata.fill(0)

def receive_audio(sock):
    """Receive audio data from server"""
    global SAMPLE_RATE, CHANNELS, CHUNK_SIZE
    
    try:
        # Receive configuration
        size_bytes = sock.recv(4)
        if not size_bytes:
            print("❌ Failed to receive configuration")
            return False
        
        config_size = int.from_bytes(size_bytes, byteorder='big')
        config_data = b''
        while len(config_data) < config_size:
            chunk = sock.recv(config_size - len(config_data))
            if not chunk:
                break
            config_data += chunk
        
        config = json.loads(config_data.decode())
        SAMPLE_RATE = config['sample_rate']
        CHANNELS = config['channels']
        CHUNK_SIZE = config['chunk_size']
        
        print(f"✓ Configuration received:")
        print(f"  Sample Rate: {SAMPLE_RATE} Hz")
        print(f"  Channels: {CHANNELS}")
        print(f"  Chunk Size: {CHUNK_SIZE}")
        
        return True
    
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def receive_loop(sock):
    """Continuously receive audio data"""
    print("\n🎵 Starting audio playback...")
    
    try:
        while True:
            # Receive chunk size
            size_bytes = sock.recv(4)
            if not size_bytes:
                print("\n❌ Connection closed by server")
                break
            
            chunk_size = int.from_bytes(size_bytes, byteorder='big')
            
            # Receive audio data
            audio_data = b''
            while len(audio_data) < chunk_size:
                chunk = sock.recv(min(BUFFER_SIZE, chunk_size - len(audio_data)))
                if not chunk:
                    break
                audio_data += chunk
            
            if len(audio_data) != chunk_size:
                print("\n❌ Incomplete audio data received")
                break
            
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
            audio_array = audio_array.reshape(-1, CHANNELS)
            
            # Add to playback queue
            try:
                audio_queue.put_nowait(audio_array)
            except queue.Full:
                # Skip frame if queue is full
                pass
    
    except Exception as e:
        print(f"\n❌ Receive error: {e}")

def list_audio_devices():
    """List available audio output devices"""
    devices = sd.query_devices()
    print("\n=== Available Audio Output Devices ===")
    for idx, device in enumerate(devices):
        if device['max_output_channels'] > 0:
            default = " (DEFAULT)" if idx == sd.default.device[1] else ""
            print(f"{idx}: {device['name']}{default}")
            print(f"   Channels: {device['max_output_channels']}")
    print()

def main():
    print("=" * 60)
    print("AUDIO STREAMING CLIENT")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("\n❌ Usage: python audio_client.py <server_ip>")
        print("Example: python audio_client.py 192.168.1.100")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    port = 5555
    
    # List available audio devices
    list_audio_devices()
    
    print(f"📡 Connecting to {server_ip}:{port}...")
    
    try:
        # Connect to server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((server_ip, port))
        print("✓ Connected to server!")
        
        # Receive configuration
        if not receive_audio(sock):
            sock.close()
            return
        
        # Start audio output stream
        with sd.OutputStream(channels=CHANNELS,
                           samplerate=SAMPLE_RATE,
                           blocksize=CHUNK_SIZE,
                           callback=audio_callback):
            
            print("✓ Audio playback started!")
            print("\n🎧 You should now hear the audio from the server")
            print("Press Ctrl+C to stop\n")
            
            # Start receiving audio
            receive_loop(sock)
    
    except ConnectionRefusedError:
        print("❌ Connection refused. Make sure the server is running.")
    except KeyboardInterrupt:
        print("\n\n⏹ Stopping client...")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        try:
            sock.close()
        except:
            pass
    
    print("✓ Client stopped.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")

