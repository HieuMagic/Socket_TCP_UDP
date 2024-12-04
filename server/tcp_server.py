# tcp_server.py
import socket
import threading
import os
import json
import signal
from pathlib import Path
import math

# Network Configuration
HOST = '192.168.31.76'
PORT = 65432
CHUNK_SIZE = 512 * 512  # 256KB chunks

class FileServer:
    """
    Multi-threaded file server that handles parallel chunk downloads.
    Reads available files from data.txt and serves them to clients.
    """
    def __init__(self):
        # Server state
        self.files_data = {}        # Dictionary of {filename: size}
        self.running = True         # Server running flag
        self.clients = set()        # Set of active client connections
        self.server_socket = None   # Main server socket
        
        # Initialize server
        self.load_files_data()
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
    def handle_shutdown(self, signum, frame):
        """Gracefully shutdown server and close all connections"""
        print("\nShutting down server...")
        self.running = False
        
        # Safely close all client connections
        for client in self.clients.copy():
            try:
                client.close()
            except:
                pass
            
        # Close main server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
    def load_files_data(self):
        """Load sizes from data.txt but validate against actual files"""
        try:
            if not os.path.exists('data.txt'):
                print("Error: data.txt not found")
                return
                
            with open('data.txt', 'r') as f:
                for line in f:
                    filename, size = line.strip().split()
                    
                    # Validate file exists
                    if not os.path.exists(filename):
                        print(f"Warning: {filename} not found")
                        continue
                        
                    # Convert size to bytes
                    if 'GB' in size:
                        size_bytes = float(size.replace('GB', '')) * 1024 * 1024 * 1024
                    else:  # MB
                        size_bytes = float(size.replace('MB', '')) * 1024 * 1024
                    
                    # Round to nearest byte
                    size_bytes = int(size_bytes)
                    
                    # Get actual file size for validation
                    actual_size = os.path.getsize(filename)
                    
                    # Accept if within 1% difference
                    if abs(actual_size - size_bytes) > (size_bytes * 0.01):
                        print(f"Warning: {filename} actual size differs by >1% from data.txt")
                    
                    # Store data.txt size but remember actual size
                    self.files_data[filename] = {
                        'listed_size': size_bytes,
                        'actual_size': actual_size
                    }
                    
            if not self.files_data:
                print("Warning: No valid files loaded")
                
        except Exception as e:
            print(f"Error loading files data: {e}")
                
    def handle_client(self, conn, addr):
        """Handle client with size validation"""
        self.clients.add(conn)
        print(f"New connection from {addr}")
        
        try:
            # Send only listed sizes
            listed_sizes = {f: data['listed_size'] 
                           for f, data in self.files_data.items()}
            conn.sendall(json.dumps(listed_sizes).encode())
            
            while self.running:
                try:
                    request = conn.recv(1024).decode('utf-8')
                    if not request:
                        break
                    
                    # Handle connection check
                    if request == "PING":
                        conn.sendall(b"PONG")
                        continue
                    
                    # Handle chunk request (format: filename:chunk_id)
                    if ':' in request:
                        filename, chunk_id = request.split(':')
                        chunk_id = int(chunk_id)
                        
                        if filename in self.files_data:
                            actual_size = self.files_data[filename]['actual_size']
                            listed_size = self.files_data[filename]['listed_size']
                            
                            # Calculate chunk boundaries using listed size
                            chunk_size = listed_size // 4
                            start = chunk_id * chunk_size
                            end = start + chunk_size if chunk_id < 3 else listed_size
                            
                            # Adjust end to not exceed actual file size
                            end = min(end, actual_size)
                            
                            # Send chunk data
                            with open(filename, 'rb') as f:
                                f.seek(start)
                                data = f.read(end - start)
                                conn.sendall(data)
                                
                    # Handle initial file request
                    else:
                        filename = request.strip()
                        if filename in self.files_data:
                            filesize = self.files_data[filename]['listed_size']
                            conn.sendall(str(filesize).encode('utf-8'))
                            conn.recv(1024)  # Wait for client OK
                        
                except socket.timeout:
                    continue
                    
        finally:
            self.clients.remove(conn)
            conn.close()
            print(f"Connection closed with {addr}")

    def start(self):
        """Start server and listen for client connections"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            self.server_socket = s
            s.bind((HOST, PORT))
            s.listen()
            print(f"Server listening on {HOST}:{PORT}")
            
            while self.running:
                try:
                    # Accept new client connections
                    conn, addr = s.accept()
                    if self.running:
                        # Start client handler thread
                        thread = threading.Thread(target=self.handle_client, 
                                               args=(conn, addr))
                        thread.daemon = True
                        thread.start()
                except:
                    if self.running:
                        print("Error accepting connection")

if __name__ == '__main__':
    server = FileServer()
    server.start()