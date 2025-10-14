import socket
import sounddevice as sd
import numpy as np
import threading
import queue
import json
import time

# ============================================================================
# CONFIGURATION - Adjust these settings to tune performance
# ============================================================================

SAMPLE_RATE = 44100      # Audio sample rate (Hz)
CHANNELS = 2             # Stereo audio
CHUNK_SIZE = 1024        # Samples per chunk (larger = more stable, higher latency)
PORT = 5555              # Server port
MAX_QUEUE_SIZE = 50      # Audio buffer size (larger = more stable, higher latency)

# Connection limits
MAX_CLIENTS = 50         # Maximum simultaneous clients (0 = unlimited)
LISTEN_BACKLOG = 10      # Pending connection queue size

# ============================================================================

clients = []
clients_lock = threading.Lock()
audio_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)

shutdown_event = threading.Event()


def find_loopback_device():
    devices = sd.query_devices()
    
    print("\nAvailable audio devices:")
    for idx, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            print(f"  [{idx}] {device['name']}")
    
    # Search for loopback device
    for idx, device in enumerate(devices):
        name_lower = device['name'].lower()
        if name_lower.__contains__('stereo mix'):
            print(f"\nFound loopback device: {device['name']}")
            return idx
    
    print("WARNING: No loopback device found!")
    return None


def audio_callback(indata, frames, time_info, status):
    if status:
        print(f"Audio status: {status}")
    try:
        audio_queue.put_nowait(indata.copy())
    except queue.Full:
        pass  # Drop frame if queue is full


def broadcast_thread():
    packet_count = 0
    while not shutdown_event.is_set():
        try:
            audio_data = audio_queue.get(timeout=1)
            audio_bytes = audio_data.tobytes()
            size = len(audio_bytes)
            
            packet_count += 1
            if packet_count % 100 == 0:  # Print every 100 packets
                print(f"\rBroadcasting... packets sent: {packet_count}, size: {size} bytes", end='', flush=True)
            
            with clients_lock:
                for client_socket, addr in clients[:]:
                    try:
                        client_socket.sendall(size.to_bytes(4, 'big'))
                        client_socket.sendall(audio_bytes)
                    except Exception as e:
                        print(f"\nClient {addr} disconnected: {e}")
                        clients.remove((client_socket, addr))
                        client_socket.close()
        
        except queue.Empty:
            continue
        except Exception as e:
            print(f"\nBroadcast error: {e}")


def accept_clients_thread(server_socket):
    server_socket.settimeout(1)
    while not shutdown_event.is_set():
        try:
            client_socket, addr = server_socket.accept()
            
            with clients_lock:                  # Using mutex for thread safety
                current_clients = len(clients)
            
            if MAX_CLIENTS > 0 and current_clients >= MAX_CLIENTS:
                print(f"Client {addr} rejected: Maximum clients ({MAX_CLIENTS}) reached")
                try:
                    error_msg = json.dumps({'error': 'Server full'}).encode()
                    client_socket.sendall(len(error_msg).to_bytes(4, 'big'))
                    client_socket.sendall(error_msg)
                except:
                    pass
                client_socket.close()
                continue
            
            client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            config = {
                'sample_rate': SAMPLE_RATE,
                'channels': CHANNELS,
                'chunk_size': CHUNK_SIZE
            }
            config_json = json.dumps(config).encode()
            client_socket.sendall(len(config_json).to_bytes(4, 'big'))
            client_socket.sendall(config_json)
            
            with clients_lock:
                clients.append((client_socket, addr))
            
            print(f"Client connected: {addr} (Total: {len(clients)})")
        
        except socket.timeout:
            continue
        except Exception as e:
            if not shutdown_event.is_set():
                print(f"Accept error: {e}")


def main():
    print("=" * 60)
    print("AURALYNC - AUDIO STREAMING SERVER")
    print("=" * 60)
    
    # Get server IP
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"Clients should connect to: {local_ip}")
    
    # Setup server socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', PORT))
    server.listen(LISTEN_BACKLOG)
    print(f"\nServer listening on port {PORT}")
    print(f"Maximum clients: {MAX_CLIENTS}")
    
    # Start threads
    threading.Thread(target=accept_clients_thread, args=(server,), daemon=True).start()
    threading.Thread(target=broadcast_thread, daemon=True).start()
    
    # Find audio device
    device_idx = find_loopback_device()
    if device_idx is None:
        print("ERROR: No audio input device found.")
        return
    
    # Start audio capture
    print(f"\nCapturing audio from device {device_idx}...")
    try:
        with sd.InputStream(
            device=device_idx,
            channels=CHANNELS,
            samplerate=SAMPLE_RATE,
            blocksize=CHUNK_SIZE,
            callback=audio_callback
        ):
            print("Broadcasting audio to clients...")
            print("Press Ctrl+C to stop")
            
            while not shutdown_event.is_set():
                time.sleep(1)
                if clients:
                    print(f"Active clients: {len(clients)}", flush=True)
    
    except KeyboardInterrupt:
        print("\n\nStopping server...")
        shutdown_event.set()
    except Exception as e:
        print(f"\nERROR: {e}")
        shutdown_event.set()
    finally:
        with clients_lock:
            for client_socket, addr in clients[:]:
                try:
                    client_socket.close()
                except:
                    pass
            clients.clear()
        
        server.close()
        time.sleep(0.5)
        print("Server stopped")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
