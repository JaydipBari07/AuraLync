import socket
import sounddevice as sd
import numpy as np
import struct

# -------- CONFIG --------
SERVER_IP = "192.168.29.88"   # Replace with your server PC's LAN IP
PORT = 50007
SAMPLE_RATE = 44100
BLOCK_SIZE = 1024
# ------------------------

def recvall(sock, length):
    """Receive exactly 'length' bytes from socket."""
    data = b""
    while len(data) < length:
        more = sock.recv(length - len(data))
        if not more:
            return None
        data += more
    return data

def main():
    print(f"🔌 Connecting to {SERVER_IP}:{PORT} ...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVER_IP, PORT))
    print("✅ Connected. Receiving audio stream...")

    with sd.OutputStream(samplerate=SAMPLE_RATE, channels=2, dtype='float32', blocksize=BLOCK_SIZE) as stream:
        while True:
            # Read packet length
            size_data = recvall(s, 4)
            if not size_data:
                break
            block_size = struct.unpack(">I", size_data)[0]

            # Read audio data
            audio_data = recvall(s, block_size)
            if not audio_data:
                break

            frame = np.frombuffer(audio_data, dtype=np.float32).reshape(-1, 2)
            stream.write(frame)

if __name__ == "__main__":
    main()
