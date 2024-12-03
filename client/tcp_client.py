# tcp_client.py
import socket
import threading
import json
import time
import os
import signal
from pathlib import Path
from threading import Lock

HOST = '192.168.31.76'
PORT = 65432
CHUNK_SIZE = 512 * 512

class FileClient:
    def __init__(self):
        self.running = True
        self.available_files = {}
        self.downloaded_files = set()
        self.socket = None
        self.print_lock = Lock()
        self.progress = {}
        signal.signal(signal.SIGINT, self.handle_interrupt)

    def handle_interrupt(self, signum, frame):
        print("\nDisconnecting...")
        self.running = False
        if self.socket:
            self.socket.close()

    def connect_to_server(self):
        try:
            if not self.socket:
                print(f"Attempting to connect to {HOST}:{PORT}...")
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((HOST, PORT))
                self.socket.settimeout(1)
                data = self.socket.recv(1024)
                print(f"Received initial data: {len(data)} bytes")
                self.available_files = json.loads(data.decode())
                self.print_available_files()
                print("Connection established successfully")
            return True
        except Exception as e:
            print(f"Connection error (detailed): {type(e).__name__}: {str(e)}")
            if self.socket:
                self.socket.close()
                self.socket = None
            return False

    def print_available_files(self):
        print("\nAvailable files:")
        for filename, size in self.available_files.items():
            print(f"{filename}: {size//(1024*1024)}MB")

    def check_connection(self):
        try:
            with self.print_lock:
                print("Sending PING...")
                self.socket.sendall(b"PING")
                response = self.socket.recv(1024)
                print(f"Received response: {response}")
                return response == b"PONG"
        except Exception as e:
            print(f"Connection check failed: {e}")
            return False

    def check_new_downloads(self):
        try:
            if not os.path.exists('input.txt'):
                return []
            
            # Read files maintaining order from input.txt
            with open('input.txt', 'r') as f:
                files = f.read().strip().split()
            
            # Keep order while filtering
            new_files = [f for f in files 
                        if f in self.available_files 
                        and f not in self.downloaded_files]
            
            if new_files:
                print("\nNew files to download:", new_files)
            return new_files
        except Exception as e:
            print(f"Error reading input.txt: {e}")
            return []

    def update_progress(self, filename, chunk_id, progress):
        """Update download progress for a chunk without excess newlines"""
        with self.print_lock:
            self.progress[f"{filename}_part{chunk_id}"] = progress
            
            # Move cursor up 4 lines first time only
            if chunk_id == 0 and progress == 0:
                print('\n' * 4)
            else:
                print('\033[4F', end='')  # Move up 4 lines
                
            # Print all progress lines
            for i in range(4):
                prog = self.progress.get(f"{filename}_part{i}", 0)
                print(f"\033[K{filename} part {i+1}.... {prog:.0f}%")  # Clear line with \033[K

    def download_chunk(self, filename, chunk_id, chunk_size):
        chunk_socket = None
        try:
            chunk_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            chunk_socket.settimeout(30)
            chunk_socket.connect((HOST, PORT))
            
            # Skip initial file list
            _ = chunk_socket.recv(1024)
            
            # Request chunk
            chunk_socket.sendall(f"{filename}:{chunk_id}".encode())
            
            # Receive and write chunk
            received = 0
            with open(f"{filename}.part{chunk_id}", 'wb') as f:
                while received < chunk_size:
                    remaining = chunk_size - received
                    data = chunk_socket.recv(min(remaining, CHUNK_SIZE))
                    if not data:
                        raise ConnectionError("Connection lost")
                    
                    f.write(data)
                    received += len(data)
                    self.update_progress(filename, chunk_id, (received/chunk_size*100))
                    
        finally:
            if chunk_socket:
                chunk_socket.close()

    def merge_chunks(self, filename):
        with open(filename, 'wb') as outfile:
            for i in range(4):
                chunk_file = f"{filename}.part{i}"
                with open(chunk_file, 'rb') as infile:
                    outfile.write(infile.read())
                os.remove(chunk_file)

    def download_file(self, filename):
        if filename in self.downloaded_files:
            return True

        try:
            # Get file size
            self.socket.sendall(filename.encode())
            filesize = int(self.socket.recv(1024).decode())
            self.socket.sendall(b"OK")
            
            # Calculate chunk sizes
            self.progress = {}
            chunk_size = filesize // 4
            chunk_sizes = [chunk_size] * 3 + [filesize - (3 * chunk_size)]
            
            # Initialize progress display
            print('\n' * 4)
            
            # Download chunks in parallel
            threads = []
            for i in range(4):
                thread = threading.Thread(
                    target=self.download_chunk,
                    args=(filename, i, chunk_sizes[i])
                )
                thread.daemon = True
                thread.start()
                threads.append(thread)
            
            for thread in threads:
                thread.join()
            
            self.merge_chunks(filename)
            self.downloaded_files.add(filename)
            print(f"\nCompleted downloading {filename}")
            return True
            
        except Exception as e:
            print(f"\nError downloading {filename}: {e}")
            return False

    def start(self):
        while self.running:
            try:
                if not self.connect_to_server() or not self.check_connection():
                    time.sleep(5)
                    continue
                
                for filename in self.check_new_downloads():
                    if self.running:
                        for attempt in range(3):
                            if self.download_file(filename):
                                break
                            print(f"Retry {attempt+1}/3 for {filename}")
                            time.sleep(1)
                
                time.sleep(5)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)

if __name__ == '__main__':
    client = FileClient()
    client.start()