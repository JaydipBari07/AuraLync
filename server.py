import socket
import soundcard as sc
import numpy as np
import struct
import time
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading

# -------- CONFIG --------
HOST = "0.0.0.0"   # Listen on all interfaces
PORT = 50007
SAMPLE_RATE = 44100
BLOCK_SIZE = 1024
# ------------------------

class AudioServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AuraLync - Audio Server")
        self.root.geometry("500x400")
        self.root.resizable(False, False)
        
        self.server_socket = None
        self.client_conn = None
        self.is_streaming = False
        self.server_thread = None
        self.mic = None
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header Frame
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, text="🎧 Audio Server", 
                              font=("Arial", 18, "bold"), 
                              bg="#2c3e50", fg="white")
        title_label.pack(pady=15)
        
        # Main content frame
        content_frame = tk.Frame(self.root, bg="#ecf0f1", padx=20, pady=20)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Server configuration
        config_frame = tk.LabelFrame(content_frame, text="Server Configuration", 
                                    font=("Arial", 10, "bold"),
                                    bg="#ecf0f1", padx=10, pady=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Port configuration
        port_frame = tk.Frame(config_frame, bg="#ecf0f1")
        port_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(port_frame, text="Port:", font=("Arial", 10), 
                bg="#ecf0f1", width=10, anchor='w').pack(side=tk.LEFT)
        self.port_entry = tk.Entry(port_frame, font=("Arial", 10), width=15)
        self.port_entry.insert(0, str(PORT))
        self.port_entry.pack(side=tk.LEFT, padx=5)
        
        # Status display
        status_frame = tk.LabelFrame(content_frame, text="Status", 
                                    font=("Arial", 10, "bold"),
                                    bg="#ecf0f1", padx=10, pady=10)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = tk.Label(status_frame, text="⚫ Stopped", 
                                     font=("Arial", 12, "bold"), 
                                     bg="#ecf0f1", fg="#e74c3c")
        self.status_label.pack(pady=5)
        
        self.info_label = tk.Label(status_frame, text="Click 'Start Server' to begin", 
                                   font=("Arial", 9), 
                                   bg="#ecf0f1", fg="#7f8c8d")
        self.info_label.pack()
        
        # Control buttons
        button_frame = tk.Frame(content_frame, bg="#ecf0f1")
        button_frame.pack(pady=10)
        
        self.start_button = tk.Button(button_frame, text="▶ Start Server", 
                                      command=self.start_server,
                                      font=("Arial", 11, "bold"),
                                      bg="#27ae60", fg="white",
                                      activebackground="#229954",
                                      activeforeground="white",
                                      relief=tk.FLAT,
                                      padx=20, pady=10,
                                      cursor="hand2")
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = tk.Button(button_frame, text="⬛ Stop Server", 
                                     command=self.stop_server,
                                     font=("Arial", 11, "bold"),
                                     bg="#e74c3c", fg="white",
                                     activebackground="#c0392b",
                                     activeforeground="white",
                                     relief=tk.FLAT,
                                     padx=20, pady=10,
                                     state=tk.DISABLED,
                                     cursor="hand2")
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Log display
        log_frame = tk.LabelFrame(content_frame, text="Log", 
                                 font=("Arial", 10, "bold"),
                                 bg="#ecf0f1", padx=5, pady=5)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, 
                                                  height=6,
                                                  font=("Consolas", 9),
                                                  bg="#ffffff",
                                                  fg="#2c3e50",
                                                  state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def log_message(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def start_server(self):
        try:
            port = int(self.port_entry.get())
        except ValueError:
            self.log_message("❌ Invalid port number")
            return
        
        self.port_entry.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        self.is_streaming = True
        self.server_thread = threading.Thread(target=self.run_server, args=(port,), daemon=True)
        self.server_thread.start()
        
    def run_server(self, port):
        try:
            # Initialize audio capture
            default_speaker = sc.default_speaker()
            self.mic = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
            
            local_ip = self.get_local_ip()
            self.log_message(f"🎧 Starting audio server...")
            self.log_message(f"📡 Listening on {local_ip}:{port}")
            
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((HOST, port))
            self.server_socket.listen(1)
            self.server_socket.settimeout(1.0)  # Timeout for checking stop signal
            
            self.root.after(0, lambda: self.status_label.config(
                text=f"🟡 Waiting for connection on {local_ip}:{port}",
                fg="#f39c12"))
            self.root.after(0, lambda: self.info_label.config(
                text=f"Streaming on {local_ip}:{port}"))
            
            while self.is_streaming:
                try:
                    self.client_conn, addr = self.server_socket.accept()
                    self.root.after(0, lambda a=addr: self.log_message(f"✅ Client connected from {a[0]}:{a[1]}"))
                    self.root.after(0, lambda: self.status_label.config(
                        text="🟢 Streaming Active",
                        fg="#27ae60"))
                    
                    # Start streaming audio
                    with self.mic.recorder(samplerate=SAMPLE_RATE) as recorder:
                        while self.is_streaming:
                            try:
                                data = recorder.record(numframes=BLOCK_SIZE)
                                data_bytes = data.astype(np.float32).tobytes()
                                self.client_conn.sendall(struct.pack(">I", len(data_bytes)) + data_bytes)
                            except:
                                break
                    
                    self.client_conn.close()
                    self.root.after(0, lambda: self.log_message("⚠️ Client disconnected"))
                    self.root.after(0, lambda: self.status_label.config(
                        text=f"🟡 Waiting for connection",
                        fg="#f39c12"))
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.is_streaming:
                        self.root.after(0, lambda e=e: self.log_message(f"❌ Error: {str(e)}"))
                    break
                    
        except Exception as e:
            self.root.after(0, lambda e=e: self.log_message(f"❌ Server error: {str(e)}"))
        finally:
            if self.server_socket:
                self.server_socket.close()
            self.root.after(0, self.cleanup_after_stop)
    
    def stop_server(self):
        self.is_streaming = False
        self.log_message("🛑 Stopping server...")
        
        if self.client_conn:
            try:
                self.client_conn.close()
            except:
                pass
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
    
    def cleanup_after_stop(self):
        self.status_label.config(text="⚫ Stopped", fg="#e74c3c")
        self.info_label.config(text="Click 'Start Server' to begin")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.port_entry.config(state=tk.NORMAL)
        
    def on_closing(self):
        if self.is_streaming:
            self.stop_server()
            time.sleep(0.5)
        self.root.destroy()

def main():
    root = tk.Tk()
    app = AudioServerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
