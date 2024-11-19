import json
import os
import socket
import threading
from pathlib import Path

# Configuration
HOST = '127.0.0.1'
PORT = 65432
CHUNK_SIZE = 1024 * 1024  # 1MB chunks

class FileServer:
    def __init__(self):
        self.files_info = {}
        self.load_files_info()
        
    def load_files_info(self):
        # Load available files and their sizes
        files_dir = Path("server_files")
        if not files_dir.exists():
            files_dir.mkdir()
            
        for file_path in files_dir.glob("*.*"):
            self.files_info[file_path.name] = os.path.getsize(file_path)
            
        # Save to files.json
        with open("files.json", "w") as f:
            json.dump(self.files_info, f, indent=2)

    def handle_client(self, conn, addr):
        try:
            while True:
                # Get command from client
                cmd = conn.recv(1024).decode()
                if not cmd:
                    break
                
                if cmd == "LIST":
                    # Send file listing
                    conn.sendall(json.dumps(self.files_info).encode())
                    
                elif cmd.startswith("GET"):
                    # Format: GET filename offset length
                    _, filename, offset, length = cmd.split()
                    offset = int(offset)
                    length = int(length)
                    
                    if filename not in self.files_info:
                        conn.sendall(b"ERROR:File not found")
                        continue
                        
                    # Send file chunk
                    with open(f"server_files/{filename}", "rb") as f:
                        f.seek(offset)
                        data = f.read(length)
                        conn.sendall(data)
                        
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
        finally:
            conn.close()

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((HOST, PORT))
        server.listen()
        
        print(f"Server listening on {HOST}:{PORT}")
        
        while True:
            conn, addr = server.accept()
            print(f"Connected by {addr}")
            thread = threading.Thread(target=self.handle_client, args=(conn, addr))
            thread.daemon = True
            thread.start()

if __name__ == "__main__":
    server = FileServer()
    server.start()