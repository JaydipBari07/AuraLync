"""
Auralync - Audio Streaming Client
Connect to server and play audio through your headphones.

Usage: python audio_client.py <server_ip>
Example: python audio_client.py 192.168.1.100

GitHub: https://github.com/yourusername/auralync
"""

import socket
import sounddevice as sd
import numpy as np
import json
import sys
import queue
import threading

# ============================================================================
# CONFIGURATION - These will be updated from server
# ============================================================================

SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK_SIZE = 1024
BUFFER_SIZE = 4096
MAX_QUEUE_SIZE = 100

# ============================================================================

audio_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)


def audio_callback(outdata, frames, time_info, status):
    if status:
        print(f"Status: {status}")
    
    try:
        outdata[:] = audio_queue.get_nowait()
    except queue.Empty:
        outdata.fill(0)  # Silence if no data


def receive_config(sock):
    global SAMPLE_RATE, CHANNELS, CHUNK_SIZE
    
    try:
        # Get config size
        size_bytes = sock.recv(4)
        if not size_bytes:
            return False
        
        config_size = int.from_bytes(size_bytes, 'big')
        
        # Get config data
        config_data = b''
        while len(config_data) < config_size:
            chunk = sock.recv(config_size - len(config_data))
            if not chunk:
                return False
            config_data += chunk
        
        # Parse config
        config = json.loads(config_data.decode())
        
        # Check if server rejected connection
        if 'error' in config:
            print(f"ERROR: {config['error']}")
            return False
        
        SAMPLE_RATE = config['sample_rate']
        CHANNELS = config['channels']
        CHUNK_SIZE = config['chunk_size']
        
        print(f"Configuration received:")
        print(f"  Sample Rate: {SAMPLE_RATE} Hz")
        print(f"  Channels: {CHANNELS}")
        print(f"  Chunk Size: {CHUNK_SIZE}")
        return True
    
    except Exception as e:
        print(f"ERROR: Config error: {e}")
        return False


def receive_audio_thread(sock):
    print("\nStarting audio playback...")
    
    packet_count = 0
    try:
        while True:
            # Get chunk size
            size_bytes = sock.recv(4)
            if not size_bytes:
                print("\nERROR: Server disconnected")
                break
            
            chunk_size = int.from_bytes(size_bytes, 'big')
            
            # Get audio data
            audio_data = b''
            while len(audio_data) < chunk_size:
                remaining = chunk_size - len(audio_data)
                chunk = sock.recv(min(BUFFER_SIZE, remaining))
                if not chunk:
                    break
                audio_data += chunk
            
            if len(audio_data) != chunk_size:
                print("\nERROR: Incomplete data received")
                break
            
            # Convert to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
            audio_array = audio_array.reshape(-1, CHANNELS)
            
            packet_count += 1
            if packet_count % 100 == 0:  # Print every 100 packets
                print(f"\rReceiving... packets: {packet_count}, queue size: {audio_queue.qsize()}", end='', flush=True)
            
            # Add to playback queue
            try:
                audio_queue.put_nowait(audio_array)
            except queue.Full:
                pass  # Drop frame if queue full
    
    except Exception as e:
        print(f"\nERROR: Receive error: {e}")


def list_output_devices():
    devices = sd.query_devices()
    print("\nAvailable audio outputs:")
    for idx, device in enumerate(devices):
        if device['max_output_channels'] > 0 and idx == sd.default.device[1]:
            default = " (DEFAULT)" if idx == sd.default.device[1] else ""
            print(f"  [{idx}] {device['name']} (DEFAULT)")
            break
    print()


def main():
    print("=" * 60)
    print("AURALYNC - AUDIO STREAMING CLIENT")
    print("=" * 60)
    
    # Check arguments
    if len(sys.argv) < 2:
        print("\nUsage: python audio_client.py <server_ip>")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    port = 5555
    
    list_output_devices()
    
    print(f"Connecting to {server_ip}:{port}...")
    
    try:
        # Connect to server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.connect((server_ip, port))
        print("Connected!")
        
        # Get configuration
        if not receive_config(sock):
            sock.close()
            return
        
        # Start audio output
        with sd.OutputStream(
            channels=CHANNELS,
            samplerate=SAMPLE_RATE,
            blocksize=CHUNK_SIZE,
            callback=audio_callback
        ):
            print("Audio playback started")
            print("\nYou should now hear audio from the server")
            print("Press Ctrl+C to stop\n")
            
            # Start receiving audio
            receive_audio_thread(sock)
    
    except ConnectionRefusedError:
        print("ERROR: Connection refused. Is the server running?")
    except KeyboardInterrupt:
        print("\n\nStopping client...")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        try:
            sock.close()
        except:
            pass
    
    print("Client stopped")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
