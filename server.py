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
        self.root.geometry("550x550")
        self.root.resizable(True, True)
        self.root.minsize(500, 450)
        
        self.server_socket = None
        self.client_connections = []  # List to track all connected clients
        self.clients_lock = threading.Lock()  # Lock for thread-safe client list access
        self.is_streaming = False
        self.server_thread = None
        self.audio_thread = None
        self.mic = None
        self.audio_buffer = None
        self.buffer_lock = threading.Lock()
        
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
                                                  height=10,
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
        
    def handle_client(self, client_conn, addr):
        """Handle individual client connection in a separate thread."""
        try:
            self.root.after(0, lambda a=addr: self.log_message(f"✅ Client connected from {a[0]}:{a[1]}"))
            
            # Add client to the list
            with self.clients_lock:
                self.client_connections.append(client_conn)
                num_clients = len(self.client_connections)
            
            self.root.after(0, lambda n=num_clients: self.status_label.config(
                text=f"🟢 Streaming to {n} client{'s' if n != 1 else ''}",
                fg="#27ae60"))
            
            # Keep connection alive and send audio data
            while self.is_streaming:
                try:
                    # Wait for new audio data
                    with self.buffer_lock:
                        if self.audio_buffer is not None:
                            data_bytes = self.audio_buffer
                        else:
                            time.sleep(0.001)
                            continue
                    
                    # Send audio data to this client
                    client_conn.sendall(struct.pack(">I", len(data_bytes)) + data_bytes)
                    
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    break
                except Exception as e:
                    if self.is_streaming:
                        self.root.after(0, lambda e=e, a=addr: self.log_message(
                            f"⚠️ Error sending to {a[0]}:{a[1]}: {str(e)}"))
                    break
                    
        except Exception as e:
            self.root.after(0, lambda e=e, a=addr: self.log_message(
                f"❌ Client handler error for {a[0]}:{a[1]}: {str(e)}"))
        finally:
            # Remove client from list
            with self.clients_lock:
                if client_conn in self.client_connections:
                    self.client_connections.remove(client_conn)
                num_clients = len(self.client_connections)
            
            try:
                client_conn.close()
            except:
                pass
            
            self.root.after(0, lambda a=addr: self.log_message(f"⚠️ Client {a[0]}:{a[1]} disconnected"))
            
            if num_clients == 0:
                self.root.after(0, lambda: self.status_label.config(
                    text="🟡 Waiting for connections",
                    fg="#f39c12"))
            else:
                self.root.after(0, lambda n=num_clients: self.status_label.config(
                    text=f"🟢 Streaming to {n} client{'s' if n != 1 else ''}",
                    fg="#27ae60"))
    
    def capture_audio(self):
        """Continuously capture audio and store it in buffer for broadcasting."""
        try:
            default_speaker = sc.default_speaker()
            self.mic = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
            
            with self.mic.recorder(samplerate=SAMPLE_RATE) as recorder:
                while self.is_streaming:
                    try:
                        data = recorder.record(numframes=BLOCK_SIZE)
                        data_bytes = data.astype(np.float32).tobytes()
                        
                        # Store audio data in buffer
                        with self.buffer_lock:
                            self.audio_buffer = data_bytes
                            
                    except Exception as e:
                        if self.is_streaming:
                            self.root.after(0, lambda e=e: self.log_message(f"⚠️ Audio capture error: {str(e)}"))
                        break
                        
        except Exception as e:
            self.root.after(0, lambda e=e: self.log_message(f"❌ Audio initialization error: {str(e)}"))
    
    def run_server(self, port):
        try:
            local_ip = self.get_local_ip()
            self.log_message(f"🎧 Starting audio server...")
            self.log_message(f"📡 Listening on {local_ip}:{port}")
            
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((HOST, port))
            self.server_socket.listen(5)  # Allow up to 5 pending connections
            self.server_socket.settimeout(1.0)  # Timeout for checking stop signal
            
            self.root.after(0, lambda: self.status_label.config(
                text=f"🟡 Waiting for connections on {local_ip}:{port}",
                fg="#f39c12"))
            self.root.after(0, lambda: self.info_label.config(
                text=f"Streaming on {local_ip}:{port}"))
            
            # Start audio capture thread
            self.audio_thread = threading.Thread(target=self.capture_audio, daemon=True)
            self.audio_thread.start()
            
            # Accept multiple client connections
            while self.is_streaming:
                try:
                    client_conn, addr = self.server_socket.accept()
                    
                    # Start a new thread to handle this client
                    client_thread = threading.Thread(
                        target=self.handle_client, 
                        args=(client_conn, addr), 
                        daemon=True
                    )
                    client_thread.start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.is_streaming:
                        self.root.after(0, lambda e=e: self.log_message(f"❌ Accept error: {str(e)}"))
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
        
        # Close all client connections
        with self.clients_lock:
            for client_conn in self.client_connections[:]:  # Make a copy of the list
                try:
                    client_conn.close()
                except:
                    pass
            self.client_connections.clear()
        
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
