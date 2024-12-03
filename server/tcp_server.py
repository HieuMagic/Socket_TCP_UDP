# tcp_server.py
import socket
import threading
import os
import json
from pathlib import Path

HOST = '192.168.31.76'
PORT = 65432
CHUNK_SIZE = 512 * 512

class FileServer:
    def __init__(self):
        self.files_data = {}
        self.load_files_data()
        
    def load_files_data(self):
        with open('data.txt', 'r') as f:
            for line in f:
                filename, size = line.strip().split()
                self.files_data[filename] = int(size.replace('MB', '')) * 1024 * 1024
                
    def handle_client(self, conn, addr):
        print(f"New connection from {addr}")
        try:
            # Send initial file list
            conn.sendall(json.dumps(self.files_data).encode())
            
            while True:
                try:
                    request = conn.recv(1024).decode('utf-8')
                    if not request:
                        break
                    
                    if request == "PING":
                        conn.sendall(b"PONG")
                        continue
                        
                    filename = request.strip()
                    if filename in self.files_data:
                        filesize = self.files_data[filename]
                        # Send size as string
                        conn.sendall(str(filesize).encode('utf-8'))
                        # Wait for client acknowledgment
                        ack = conn.recv(1024)
                        if ack != b"OK":
                            continue
                        
                        with open(filename, 'rb') as f:
                            for i in range(4):
                                chunk_size = filesize // 4
                                start = i * chunk_size
                                end = start + chunk_size if i < 3 else filesize
                                f.seek(start)
                                
                                # Send chunk in smaller pieces
                                data = f.read(end - start)
                                total_sent = 0
                                while total_sent < len(data):
                                    sent = conn.send(data[total_sent:total_sent + CHUNK_SIZE])
                                    total_sent += sent
                                
                                # Wait for next chunk acknowledgment    
                                ack = conn.recv(1024)
                                if ack != b"NEXT":
                                    break
                                
                except socket.timeout:
                    continue
                    
        except ConnectionResetError:
            print(f"Client {addr} disconnected")
        finally:
            conn.close()
            print(f"Connection closed with {addr}")

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, PORT))
            s.listen()
            print(f"Server listening on {HOST}:{PORT}")
            
            while True:
                conn, addr = s.accept()
                thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                thread.daemon = True
                thread.start()

if __name__ == '__main__':
    server = FileServer()
    server.start()