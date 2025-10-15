import socket
import sounddevice as sd
import numpy as np
import struct
import time
import threading
import queue

# -------- CONFIG --------
HOST = "0.0.0.0"   # Listen on all interfaces
PORT = 50007
SAMPLE_RATE = 44100
BLOCK_SIZE = 1024
CHANNELS = 2  # Stereo
# ------------------------

# Global variables
clients = []
clients_lock = threading.Lock()
audio_queue = queue.Queue(maxsize=50)
shutdown_event = threading.Event()


def select_input_device():
    """Auto-select loopback device (Stereo Mix) for capturing system audio"""
    devices = sd.query_devices()
    
    # First priority: Look for "Stereo Mix" which is the standard Windows loopback
    # This is what soundcard's loopback functionality uses
    best_match = None
    for idx, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            name_lower = device['name'].lower()
            if 'stereo mix' in name_lower:
                # Prefer non-Microsoft sound mapper versions
                if 'microsoft' not in name_lower and 'mapper' not in name_lower:
                    best_match = (idx, device)
                    break
                elif best_match is None:
                    best_match = (idx, device)
    
    if best_match:
        idx, device = best_match
        print(f"\n✅ Using loopback device: [{idx}] {device['name']}")
        print("   (Capturing system audio output)")
        return idx
    
    # Fallback: Look for other loopback-like devices
    for idx, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            name_lower = device['name'].lower()
            if 'wave out mix' in name_lower or 'loopback' in name_lower:
                print(f"\n✅ Using loopback device: [{idx}] {device['name']}")
                return idx
    
    # Last resort: Show all input devices and let user choose
    print("\n⚠️  WARNING: No loopback device (Stereo Mix) found!")
    print("   Please enable 'Stereo Mix' in Windows Sound settings for system audio capture.")
    print("\nAvailable INPUT devices:")
    input_devices = []
    for idx, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            input_devices.append((idx, device))
            print(f"  [{idx}] {device['name']}")
    
    if not input_devices:
        print("❌ ERROR: No input devices found!")
        return None
    
    while True:
        choice = input("\nEnter device number: ").strip()
        if choice.isdigit():
            selected = int(choice)
            if any(selected == idx for idx, _ in input_devices):
                return selected
        print("Invalid device number!")


def audio_callback(indata, frames, time_info, status):
    """Called by sounddevice when audio data is available"""
    if status:
        print(f"⚠️  Audio status: {status}")
    try:
        audio_queue.put_nowait(indata.copy().tobytes())
    except queue.Full:
        pass  # Drop frame if queue full


def broadcast_thread():
    """Broadcast audio data to all connected clients"""
    while not shutdown_event.is_set():
        try:
            audio_data = audio_queue.get(timeout=1)
            packet = struct.pack(">I", len(audio_data)) + audio_data
            
            with clients_lock:
                for client_socket, addr in clients[:]:
                    try:
                        client_socket.sendall(packet)
                    except Exception as e:
                        print(f"❌ Client {addr} disconnected: {e}")
                        clients.remove((client_socket, addr))
                        client_socket.close()
                        print(f"📊 Active clients: {len(clients)}")
        except queue.Empty:
            continue


def accept_clients_thread(server_socket):
    """Accept new client connections"""
    server_socket.settimeout(1)
    while not shutdown_event.is_set():
        try:
            conn, addr = server_socket.accept()
            with clients_lock:
                clients.append((conn, addr))
            print(f"✅ Client connected from {addr} (Total: {len(clients)})")
        except socket.timeout:
            continue
        except Exception as e:
            if not shutdown_event.is_set():
                print(f"❌ Accept error: {e}")


def main():
    print("=" * 60)
    print("🎧 AUDIO STREAMING SERVER")
    print("=" * 60)
    
    # Get server IP
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    # Setup server socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    
    print(f"\n✅ Server listening on port {PORT}")
    print("\n" + "=" * 60)
    print("📡 CLIENTS SHOULD CONNECT TO:")
    print("=" * 60)
    print(f"\n  From THIS machine:")
    print(f"    python client.py 127.0.0.1")
    print(f"\n  From OTHER machines:")
    print(f"    python client.py {local_ip}")
    print("\n" + "=" * 60)
    
    # Select audio device
    device_idx = select_input_device()
    if device_idx is None:
        print("❌ No device selected. Exiting.")
        return
    
    # Start threads
    threading.Thread(target=broadcast_thread, daemon=True).start()
    threading.Thread(target=accept_clients_thread, args=(server,), daemon=True).start()
    
    print(f"\n🎤 Starting audio capture from device [{device_idx}]...")
    print("🎵 Server running. Press Ctrl+C to stop\n")
    
    try:
        with sd.InputStream(
            device=device_idx,
            channels=CHANNELS,
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            callback=audio_callback
        ):
            while not shutdown_event.is_set():
                time.sleep(1)
                if clients:
                    with clients_lock:
                        count = len(clients)
                    if count > 0:
                        print(f"\r📊 Active clients: {count}  ", end="", flush=True)
    
    except KeyboardInterrupt:
        print("\n\n⏹  Stopping server...")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
    finally:
        shutdown_event.set()
        with clients_lock:
            for client_socket, addr in clients[:]:
                try:
                    client_socket.close()
                except:
                    pass
            clients.clear()
        server.close()
        print("✅ Server stopped")


if __name__ == "__main__":
    main()
