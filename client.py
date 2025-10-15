import socket
import sounddevice as sd
import numpy as np
import struct
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
from queue import Queue, Empty

# -------- CONFIG --------
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

class AudioClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AuraLync - Audio Client")
        self.root.geometry("550x600")
        self.root.resizable(True, True)
        self.root.minsize(500, 500)
        
        self.socket = None
        self.is_connected = False
        self.client_thread = None
        self.stream = None
        self.audio_queue = Queue(maxsize=20)  # Buffer for smooth playback
        
        # Get available audio devices
        self.audio_devices = self.get_output_devices()
        self.selected_device = None
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header Frame
        header_frame = tk.Frame(self.root, bg="#34495e", height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, text="🔊 Audio Client", 
                              font=("Arial", 18, "bold"), 
                              bg="#34495e", fg="white")
        title_label.pack(pady=15)
        
        # Main content frame
        content_frame = tk.Frame(self.root, bg="#ecf0f1", padx=20, pady=20)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Connection configuration
        config_frame = tk.LabelFrame(content_frame, text="Server Connection", 
                                    font=("Arial", 10, "bold"),
                                    bg="#ecf0f1", padx=10, pady=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        # IP Address input
        ip_frame = tk.Frame(config_frame, bg="#ecf0f1")
        ip_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(ip_frame, text="Server IP:", font=("Arial", 10), 
                bg="#ecf0f1", width=12, anchor='w').pack(side=tk.LEFT)
        self.ip_entry = tk.Entry(ip_frame, font=("Arial", 10), width=20)
        self.ip_entry.insert(0, "192.168.1.100")  # Default placeholder
        self.ip_entry.pack(side=tk.LEFT, padx=5)
        
        # Port input
        port_frame = tk.Frame(config_frame, bg="#ecf0f1")
        port_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(port_frame, text="Port:", font=("Arial", 10), 
                bg="#ecf0f1", width=12, anchor='w').pack(side=tk.LEFT)
        self.port_entry = tk.Entry(port_frame, font=("Arial", 10), width=20)
        self.port_entry.insert(0, str(PORT))
        self.port_entry.pack(side=tk.LEFT, padx=5)
        
        # Audio device selection
        device_frame = tk.Frame(config_frame, bg="#ecf0f1")
        device_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(device_frame, text="Output Device:", font=("Arial", 10), 
                bg="#ecf0f1", width=12, anchor='w').pack(side=tk.LEFT)
        
        device_names = [dev['name'] for dev in self.audio_devices]
        self.device_combo = ttk.Combobox(device_frame, 
                                         values=device_names,
                                         font=("Arial", 9),
                                         state="readonly",
                                         width=35)
        if device_names:
            self.device_combo.current(0)  # Select first device by default
        self.device_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Refresh button for devices
        refresh_btn = tk.Button(device_frame, text="🔄", 
                               command=self.refresh_devices,
                               font=("Arial", 10),
                               bg="#95a5a6", fg="white",
                               relief=tk.FLAT,
                               padx=8, pady=2,
                               cursor="hand2")
        refresh_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # Status display
        status_frame = tk.LabelFrame(content_frame, text="Status", 
                                    font=("Arial", 10, "bold"),
                                    bg="#ecf0f1", padx=10, pady=10)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = tk.Label(status_frame, text="⚫ Disconnected", 
                                     font=("Arial", 12, "bold"), 
                                     bg="#ecf0f1", fg="#e74c3c")
        self.status_label.pack(pady=5)
        
        self.info_label = tk.Label(status_frame, text="Enter server IP:PORT and click 'Connect'", 
                                   font=("Arial", 9), 
                                   bg="#ecf0f1", fg="#7f8c8d")
        self.info_label.pack()
        
        # Control buttons
        button_frame = tk.Frame(content_frame, bg="#ecf0f1")
        button_frame.pack(pady=10)
        
        self.connect_button = tk.Button(button_frame, text="🔌 Connect", 
                                        command=self.connect_to_server,
                                        font=("Arial", 11, "bold"),
                                        bg="#3498db", fg="white",
                                        activebackground="#2980b9",
                                        activeforeground="white",
                                        relief=tk.FLAT,
                                        padx=20, pady=10,
                                        cursor="hand2")
        self.connect_button.pack(side=tk.LEFT, padx=5)
        
        self.disconnect_button = tk.Button(button_frame, text="✖ Disconnect", 
                                           command=self.disconnect_from_server,
                                           font=("Arial", 11, "bold"),
                                           bg="#e74c3c", fg="white",
                                           activebackground="#c0392b",
                                           activeforeground="white",
                                           relief=tk.FLAT,
                                           padx=20, pady=10,
                                           state=tk.DISABLED,
                                           cursor="hand2")
        self.disconnect_button.pack(side=tk.LEFT, padx=5)
        
        # Log display
        log_frame = tk.LabelFrame(content_frame, text="Log", 
                                 font=("Arial", 10, "bold"),
                                 bg="#ecf0f1", padx=5, pady=5)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, 
                                                  height=12,
                                                  font=("Consolas", 9),
                                                  bg="#ffffff",
                                                  fg="#2c3e50",
                                                  state=tk.DISABLED,
                                                  wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def log_message(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def get_output_devices(self):
        """Get list of available output audio devices."""
        devices = []
        try:
            device_list = sd.query_devices()
            for i, device in enumerate(device_list):
                if device['max_output_channels'] > 0:  # Output device
                    devices.append({
                        'index': i,
                        'name': device['name'],
                        'channels': device['max_output_channels']
                    })
            if not devices:
                devices.append({'index': None, 'name': 'Default Device', 'channels': 2})
        except Exception as e:
            self.log_message(f"⚠️ Error querying devices: {str(e)}")
            devices.append({'index': None, 'name': 'Default Device', 'channels': 2})
        return devices
    
    def refresh_devices(self):
        """Refresh the list of audio devices."""
        if self.is_connected:
            self.log_message("⚠️ Cannot refresh devices while connected")
            return
        
        self.audio_devices = self.get_output_devices()
        device_names = [dev['name'] for dev in self.audio_devices]
        self.device_combo['values'] = device_names
        if device_names:
            self.device_combo.current(0)
        self.log_message("🔄 Audio devices refreshed")
        
    def connect_to_server(self):
        server_ip = self.ip_entry.get().strip()
        
        try:
            port = int(self.port_entry.get())
        except ValueError:
            self.log_message("❌ Invalid port number")
            return
        
        if not server_ip:
            self.log_message("❌ Please enter server IP address")
            return
        
        # Get selected audio device
        selected_idx = self.device_combo.current()
        if selected_idx >= 0 and selected_idx < len(self.audio_devices):
            self.selected_device = self.audio_devices[selected_idx]['index']
            device_name = self.audio_devices[selected_idx]['name']
            self.log_message(f"🔊 Using output device: {device_name}")
        else:
            self.selected_device = None
            self.log_message("🔊 Using default output device")
        
        self.ip_entry.config(state=tk.DISABLED)
        self.port_entry.config(state=tk.DISABLED)
        self.device_combo.config(state=tk.DISABLED)
        self.connect_button.config(state=tk.DISABLED)
        self.disconnect_button.config(state=tk.NORMAL)
        
        self.is_connected = True
        self.client_thread = threading.Thread(target=self.run_client, 
                                              args=(server_ip, port), 
                                              daemon=True)
        self.client_thread.start()
        
    def audio_callback(self, outdata, frames, time_info, status):
        """Audio callback function for smooth playback."""
        try:
            data = self.audio_queue.get_nowait()
            frame = np.frombuffer(data, dtype=np.float32).reshape(-1, 2)
            if len(frame) < frames:
                # Pad with zeros if needed
                outdata[:len(frame)] = frame
                outdata[len(frame):] = 0
            else:
                outdata[:] = frame[:frames]
        except Empty:
            # No data available, output silence
            outdata.fill(0)
    
    def receive_audio_data(self, server_ip, port):
        """Separate thread to receive audio data and fill the queue."""
        try:
            while self.is_connected:
                try:
                    # Read packet length
                    size_data = recvall(self.socket, 4)
                    if not size_data:
                        break
                    block_size = struct.unpack(">I", size_data)[0]
                    
                    # Read audio data
                    audio_data = recvall(self.socket, block_size)
                    if not audio_data:
                        break
                    
                    # Put data in queue (blocking until space available)
                    self.audio_queue.put(audio_data, timeout=1.0)
                    
                except Exception as e:
                    if self.is_connected:
                        self.root.after(0, lambda e=e: self.log_message(f"⚠️ Receive error: {str(e)}"))
                    break
                    
        except Exception as e:
            if self.is_connected:
                self.root.after(0, lambda e=e: self.log_message(f"❌ Receiver error: {str(e)}"))
    
    def run_client(self, server_ip, port):
        try:
            self.root.after(0, lambda: self.log_message(f"🔌 Connecting to {server_ip}:{port}..."))
            self.root.after(0, lambda: self.status_label.config(
                text="🟡 Connecting...",
                fg="#f39c12"))
            
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)  # Connection timeout
            self.socket.connect((server_ip, port))
            self.socket.settimeout(None)  # Reset timeout after connection
            
            self.root.after(0, lambda: self.log_message("✅ Connected! Receiving audio stream..."))
            self.root.after(0, lambda: self.status_label.config(
                text=f"🟢 Connected to {server_ip}:{port}",
                fg="#27ae60"))
            self.root.after(0, lambda: self.info_label.config(
                text=f"Streaming from {server_ip}:{port}"))
            
            # Clear the queue
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except Empty:
                    break
            
            # Start receiver thread
            receiver_thread = threading.Thread(
                target=self.receive_audio_data, 
                args=(server_ip, port), 
                daemon=True
            )
            receiver_thread.start()
            
            # Start audio output stream with callback
            with sd.OutputStream(samplerate=SAMPLE_RATE, channels=2, 
                               dtype='float32', blocksize=BLOCK_SIZE,
                               callback=self.audio_callback,
                               device=self.selected_device) as self.stream:
                # Wait until disconnected
                while self.is_connected:
                    sd.sleep(100)  # Sleep in 100ms intervals
            
            if self.is_connected:
                self.root.after(0, lambda: self.log_message("⚠️ Connection lost"))
                
        except socket.timeout:
            self.root.after(0, lambda: self.log_message("❌ Connection timeout"))
        except ConnectionRefusedError:
            self.root.after(0, lambda: self.log_message("❌ Connection refused. Is the server running?"))
        except Exception as e:
            self.root.after(0, lambda e=e: self.log_message(f"❌ Error: {str(e)}"))
        finally:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
            self.root.after(0, self.cleanup_after_disconnect)
    
    def disconnect_from_server(self):
        self.is_connected = False
        self.log_message("🛑 Disconnecting...")
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        
        # Clear the audio queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except Empty:
                break
    
    def cleanup_after_disconnect(self):
        self.status_label.config(text="⚫ Disconnected", fg="#e74c3c")
        self.info_label.config(text="Enter server IP:PORT and click 'Connect'")
        self.connect_button.config(state=tk.NORMAL)
        self.disconnect_button.config(state=tk.DISABLED)
        self.ip_entry.config(state=tk.NORMAL)
        self.port_entry.config(state=tk.NORMAL)
        self.device_combo.config(state="readonly")
        
    def on_closing(self):
        if self.is_connected:
            self.disconnect_from_server()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = AudioClientGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
