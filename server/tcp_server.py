# tcp_server.py
import socket
import threading
import os
import json
import signal
from pathlib import Path

HOST = '192.168.31.76'
PORT = 65432
CHUNK_SIZE = 512 * 512

class FileServer:
    def __init__(self):
        self.files_data = {}
        self.running = True
        self.clients = set()  # Track active client connections
        self.server_socket = None
        self.load_files_data()
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
    def handle_shutdown(self, signum, frame):
        print("\nShutting down server...")
        self.running = False
        
        # Close all client connections
        for client in self.clients.copy():
            try:
                client.close()
            except:
                pass
            
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
    def load_files_data(self):
        with open('data.txt', 'r') as f:
            for line in f:
                filename, size = line.strip().split()
                self.files_data[filename] = int(size.replace('MB', '')) * 1024 * 1024
                
    def handle_client(self, conn, addr):
        self.clients.add(conn)
        print(f"New connection from {addr}")
        try:
            conn.sendall(json.dumps(self.files_data).encode())
            
            while self.running:
                try:
                    request = conn.recv(1024).decode('utf-8')
                    if not request:
                        break
                        
                    if request == "PING":
                        conn.sendall(b"PONG")
                        continue
                        
                    if ':' in request:  # Chunk request
                        filename, chunk_id = request.split(':')
                        chunk_id = int(chunk_id)
                        if filename in self.files_data:
                            filesize = self.files_data[filename]
                            chunk_size = filesize // 4
                            start = chunk_id * chunk_size
                            end = start + chunk_size if chunk_id < 3 else filesize
                            
                            with open(filename, 'rb') as f:
                                f.seek(start)
                                data = f.read(end - start)
                                conn.sendall(data)
                    else:  # Initial file request
                        filename = request.strip()
                        if filename in self.files_data:
                            filesize = self.files_data[filename]
                            conn.sendall(str(filesize).encode('utf-8'))
                            conn.recv(1024)  # Wait for OK
                        
                except socket.timeout:
                    continue
                    
        finally:
            self.clients.remove(conn)
            conn.close()
            print(f"Connection closed with {addr}")

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            self.server_socket = s
            s.bind((HOST, PORT))
            s.listen()
            print(f"Server listening on {HOST}:{PORT}")
            
            while self.running:
                try:
                    conn, addr = s.accept()
                    if self.running:  # Double check before starting thread
                        thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                        thread.daemon = True
                        thread.start()
                except:
                    if self.running:  # Only print error if not shutting down
                        print("Error accepting connection")

if __name__ == '__main__':
    server = FileServer()
    server.start()