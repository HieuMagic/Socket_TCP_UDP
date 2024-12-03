# tcp_client.py
import socket
import threading
import json
import time
import os
import signal
from pathlib import Path

HOST = '192.168.31.76'
PORT = 65432
CHUNK_SIZE = 512 * 512

class FileClient:
    def __init__(self):
        self.running = True
        self.available_files = {}
        self.downloaded_files = set()
        self.socket = None
        signal.signal(signal.SIGINT, self.handle_interrupt)
        # Add print lock for synchronized console output
        self.print_lock = threading.Lock()
        
    def handle_interrupt(self, signum, frame):
        print("\nDisconnecting...")
        self.running = False
        if self.socket:
            self.socket.close()

    def connect_to_server(self):
        if not self.socket:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(1)  # 1 second timeout for operations
            self.socket.connect((HOST, PORT))
            self.available_files = json.loads(self.socket.recv(1024).decode())
            print("\nAvailable files:")
            for filename, size in self.available_files.items():
                print(f"{filename}: {size//(1024*1024)}MB")

    def check_connection(self):
        try:
            self.socket.sendall(b"PING")
            response = self.socket.recv(1024)
            return response == b"PONG"
        except:
            return False

    def check_new_downloads(self):
        if not os.path.exists('input.txt'):
            return []
            
        with open('input.txt', 'r') as f:
            files_to_download = f.read().strip().split()
            
        new_files = [f for f in files_to_download 
                    if f in self.available_files 
                    and f not in self.downloaded_files]
        
        if new_files:
            print("\nNew files to download:", new_files)
        return new_files

    def download_chunk(self, filename, chunk_id, start, size, data):
        temp_file = f"{filename}.part{chunk_id}"
        with open(temp_file, 'wb') as f:
            f.write(data)
        with self.print_lock:
            print(f"Downloading {filename} part {chunk_id+1}.... {(len(data)/size)*100:.0f}%")
        
    def merge_chunks(self, filename):
        with open(filename, 'wb') as outfile:
            for i in range(4):
                chunk_file = f"{filename}.part{i}"
                with open(chunk_file, 'rb') as infile:
                    outfile.write(infile.read())
                os.remove(chunk_file)
                
    def download_file(self, s, filename):
        if filename in self.downloaded_files:
            return
            
        try:
            s.settimeout(30)
            # Send filename as text
            s.sendall(filename.encode('utf-8'))
            
            # Receive file size as text
            filesize = int(s.recv(1024).decode('utf-8'))
            s.sendall(b"OK")
            
            chunk_size = filesize // 4
            
            for i in range(4):
                start = i * chunk_size
                end = start + chunk_size if i < 3 else filesize
                size = end - start
                
                data = b''
                received = 0
                
                while received < size:
                    remaining = size - received
                    packet = s.recv(min(remaining, CHUNK_SIZE))
                    if not packet:
                        raise ConnectionError("Connection lost during transfer")
                    
                    data += packet
                    received += len(packet)
                    
                    # Update progress
                    progress = (received / size) * 100
                    print(f"\rDownloading {filename} part {i+1}.... {progress:.0f}%", end='', flush=True)
                
                print()  # New line after chunk
                
                # Write chunk immediately
                temp_file = f"{filename}.part{i}"
                with open(temp_file, 'wb') as f:
                    f.write(data)
                    
                s.sendall(b"NEXT")
            
            # Merge chunks
            self.merge_chunks(filename)
            self.downloaded_files.add(filename)
            print(f"\nCompleted downloading {filename}")
            
        except socket.timeout:
            print(f"\nTimeout while downloading {filename}")
            return False
        except Exception as e:
            print(f"\nError downloading {filename}: {e}")
            return False
        finally:
            s.settimeout(1)
        
        return True

    def start(self):
        try:
            self.connect_to_server()
            
            while self.running:
                if not self.check_connection():
                    print("Lost connection to server")
                    break
                    
                new_files = self.check_new_downloads()
                for filename in new_files:
                    if self.running:
                        retry_count = 3
                        while retry_count > 0:
                            if self.download_file(self.socket, filename):
                                break
                            retry_count -= 1
                            print(f"Retrying download of {filename}... ({retry_count} attempts left)")
                            time.sleep(1)
                            
                time.sleep(5)
                
        except ConnectionRefusedError:
            print("Could not connect to server")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            if self.socket:
                self.socket.close()

if __name__ == '__main__':
    client = FileClient()
    client.start()