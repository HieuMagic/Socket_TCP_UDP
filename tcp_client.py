import json
import socket
import threading
import time
import os
from pathlib import Path

# Configuration
HOST = '127.0.0.1'
PORT = 65432
THREADS = 4
CHECK_INTERVAL = 5  # seconds

class FileDownloader:
    def __init__(self):
        self.files_info = {}
        self.downloaded_files = set()
        self.current_file = None
        self.progress = [0] * THREADS
        
    def get_server_files(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            s.sendall(b"LIST")
            self.files_info = json.loads(s.recv(4096).decode())
            
    def download_chunk(self, filename, start, length, thread_id):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, PORT))
                cmd = f"GET {filename} {start} {length}"
                s.sendall(cmd.encode())
                
                # Receive and write chunk
                received = 0
                chunk_path = f"downloads/{filename}.part{thread_id}"
                
                with open(chunk_path, "wb") as f:
                    while received < length:
                        data = s.recv(min(4096, length - received))
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                        self.progress[thread_id] = int((received / length) * 100)
                        
        except Exception as e:
            print(f"Error downloading chunk {thread_id}: {e}")

    def download_file(self, filename):
        if filename not in self.files_info:
            print(f"File {filename} not found on server")
            return
            
        self.current_file = filename
        file_size = self.files_info[filename]
        chunk_size = file_size // THREADS
        threads = []
        
        # Create downloads directory
        Path("downloads").mkdir(exist_ok=True)
        
        # Start download threads
        for i in range(THREADS):
            start = i * chunk_size
            length = chunk_size if i < THREADS-1 else file_size - start
            thread = threading.Thread(
                target=self.download_chunk,
                args=(filename, start, length, i)
            )
            thread.start()
            threads.append(thread)
            
        # Show progress
        while any(thread.is_alive() for thread in threads):
            print("\033[H\033[J")  # Clear screen
            for i in range(THREADS):
                print(f"Downloading {filename} part {i+1} .... {self.progress[i]}%")
            time.sleep(0.1)
            
        # Wait for all threads
        for thread in threads:
            thread.join()
            
        # Combine chunks
        with open(f"downloads/{filename}", "wb") as outfile:
            for i in range(THREADS):
                chunk_path = f"downloads/{filename}.part{i}"
                with open(chunk_path, "rb") as infile:
                    outfile.write(infile.read())
                os.remove(chunk_path)
                
        self.downloaded_files.add(filename)
        self.current_file = None
        print(f"\nDownloaded {filename}")

    def check_input_file(self):
        try:
            with open("input.txt", "r") as f:
                files = f.read().splitlines()
            
            for filename in files:
                if filename and filename not in self.downloaded_files:
                    self.download_file(filename)
                    
        except FileNotFoundError:
            pass

    def start(self):
        print("Starting download client...")
        self.get_server_files()
        print("\nAvailable files:")
        for filename, size in self.files_info.items():
            print(f"{filename}: {size} bytes")
            
        try:
            while True:
                self.check_input_file()
                time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("\nShutting down...")

if __name__ == "__main__":
    client = FileDownloader()
    client.start()
