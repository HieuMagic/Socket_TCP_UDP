import json
import os
import socket
import threading
import signal
import shutil
from pathlib import Path

# Configuration
HOST = '192.168.31.76'
PORT = 65432
CHUNK_SIZE = 1024 * 1024  # 1MB chunks

class FileServer:
    def __init__(self):
        self.files_info = {}
        self.running = True
        self.server_socket = None
        self.load_files_info()
        self.setup_signal_handlers()
        
    def setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
    def handle_shutdown(self, signum, frame):
        print("\nShutting down server...")
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        self.cleanup()
        
    def cleanup(self):
        """Remove temporary files and folders"""
        try:
            # Remove files.json if it exists
            if os.path.exists("files.json"):
                os.remove("files.json")
                print("Removed files.json")
                
            # Remove downloads directory if it exists
            if os.path.exists("downloads"):
                shutil.rmtree("downloads")
                print("Removed downloads directory")
        except Exception as e:
            print(f"Error during cleanup: {e}")
            
    def load_files_info(self):
        # Load available files and their sizes
        files_dir = Path("TCP_UDP_Data")
        if not files_dir.exists():
            files_dir.mkdir()
            
        for file_path in files_dir.glob("*.*"):
            self.files_info[file_path.name] = os.path.getsize(file_path)
            
        # Save to files.json
        with open("files.json", "w") as f:
            json.dump(self.files_info, f, indent=2)

    def handle_client(self, conn, addr):
        try:
            while self.running:
                cmd = conn.recv(1024).decode()
                if not cmd:
                    break
                
                if cmd == "LIST":
                    conn.sendall(json.dumps(self.files_info).encode())
                    print(f"Client {addr} requested file list")
                    
                elif cmd.startswith("GET"):
                    # Format: GET filename offset length
                    _, filename, offset, length = cmd.split()
                    offset = int(offset)
                    length = int(length)
                    
                    if filename not in self.files_info:
                        conn.sendall(b"ERROR:File not found")
                        continue
                        
                    # Send file chunk and track progress
                    chunk_number = offset // CHUNK_SIZE
                    total_chunks = self.files_info[filename] // CHUNK_SIZE + 1
                    
                    print(f"Client {addr} downloading {filename} chunk {chunk_number+1}/{total_chunks}")
                    
                    with open(f"TCP_UDP_Data/{filename}", "rb") as f:
                        f.seek(offset)
                        data = f.read(length)
                        conn.sendall(data)
                        
                    print(f"Sent chunk {chunk_number+1}/{total_chunks} of {filename} to {addr}")
                    
                    # If this was the last chunk
                    if (offset + length) >= self.files_info[filename]:
                        print(f"Completed transfer of {filename} to {addr}")
                        
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
        finally:
            print(f"Client {addr} disconnected")
            conn.close()

    def start(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Allow reuse of address
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Make socket non-blocking
            self.server_socket.settimeout(1)
            self.server_socket.bind((HOST, PORT))
            self.server_socket.listen()
            
            print(f"Server listening on {HOST}:{PORT}")
            print("Press Ctrl+C to shutdown")
            
            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    print(f"Connected by {addr}")
                    thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                    thread.daemon = True
                    thread.start()
                except socket.timeout:
                    # Check running flag periodically
                    continue
                except socket.error as e:
                    if not self.running:
                        break
                    print(f"Socket error: {e}")

        except KeyboardInterrupt:
            print("\nReceived keyboard interrupt, shutting down...")
        finally:
            self.running = False
            if self.server_socket:
                self.server_socket.close()
            print("Server stopped")

if __name__ == "__main__":
    server = FileServer()
    server.start()