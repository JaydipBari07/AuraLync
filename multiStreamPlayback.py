import socket
import soundcard as sc
import numpy as np
import struct
import time

# -------- CONFIG --------
HOST = "0.0.0.0"   # Listen on all interfaces
PORT = 50007
SAMPLE_RATE = 44100
BLOCK_SIZE = 1024
# ------------------------

# Capture system audio (loopback)
default_speaker = sc.default_speaker()
mic = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)

def main():
    print(f"🎧 Starting audio server on port {PORT} ...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen(1)
    conn, addr = s.accept()
    print(f"✅ Client connected from {addr}")

    with mic.recorder(samplerate=SAMPLE_RATE) as recorder:
        while True:
            data = recorder.record(numframes=BLOCK_SIZE)
            data_bytes = data.astype(np.float32).tobytes()
            # Prefix with size for each block
            conn.sendall(struct.pack(">I", len(data_bytes)) + data_bytes)

if __name__ == "__main__":
    main()
