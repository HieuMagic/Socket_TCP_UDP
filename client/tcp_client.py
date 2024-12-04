# tcp_client.py
import socket
import threading
import json
import time
import os
import signal
from pathlib import Path
from threading import Lock

# Network Configuration
HOST = '192.168.31.76'
PORT = 65432
CHUNK_SIZE = 512 * 512  # 256KB chunks

class FileClient:
    """
    Multi-threaded file client that downloads files in parallel chunks.
    Monitors input.txt for new download requests.
    """
    def __init__(self):
        # Client state
        self.running = True         # Client running flag
        self.available_files = {}   # Dictionary of {filename: size}
        self.downloaded_files = set() # Set of completed downloads
        self.socket = None          # Main connection socket
        self.print_lock = Lock()    # Synchronize console output
        self.progress = {}          # Track download progress
        
        # Register Ctrl+C handler
        signal.signal(signal.SIGINT, self.handle_interrupt)

    def handle_interrupt(self, signum, frame):
        """Handle graceful shutdown on Ctrl+C"""
        print("\nDisconnecting...")
        self.running = False
        if self.socket:
            self.socket.close()

    def connect_to_server(self):
        """Establish connection and get available files from server"""
        try:
            if not self.socket:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(5)  # Initial connection timeout
                print(f"Connecting to {HOST}:{PORT}...")
                self.socket.connect((HOST, PORT))
                self.socket.settimeout(1)  # Regular operation timeout
                
                # Get and validate file list
                data = self.socket.recv(1024)
                if not data:
                    print("Error: No data received from server")
                    return False
                    
                self.available_files = json.loads(data.decode())
                if not self.available_files:
                    print("Warning: No files available on server")
                    return False
                    
                self.print_available_files()
                return True
                
        except ConnectionRefusedError:
            print(f"Error: Connection refused - is server running on {HOST}:{PORT}?")
            return False
        except json.JSONDecodeError:
            print("Error: Invalid data received from server")
            return False
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def print_available_files(self):
        """Display available files and their sizes"""
        print("\nAvailable files:")
        for filename, size in self.available_files.items():
            print(f"{filename}: {size//(1024*1024)}MB")

    def check_connection(self):
        """Verify server connection is alive with ping/pong"""
        try:
            with self.print_lock:
                self.socket.sendall(b"PING")
                return self.socket.recv(1024) == b"PONG"
        except:
            return False

    def check_new_downloads(self):
        """
        Monitor input.txt for new download requests.
        Returns list of new files to download in order.
        """
        try:
            # Validate input.txt existence and permissions
            if not os.path.exists('input.txt'):
                print("Warning: input.txt not found")
                return []
                
            if not os.access('input.txt', os.R_OK):
                print("Error: input.txt not readable")
                return []
                
            # Read and parse input file
            with open('input.txt', 'r') as f:
                files = f.read().strip().split()
                
            if not files:
                print("Warning: input.txt is empty")
                return []
                
            # Filter for new, available files
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
        """Update download progress display for all chunks"""
        with self.print_lock:
            self.progress[f"{filename}_part{chunk_id}"] = progress
            
            # Handle initial display setup
            if chunk_id == 0 and progress == 0:
                print('\n' * 4)
            else:
                print('\033[4F', end='')  # Move cursor up 4 lines
                
            # Update all progress lines
            for i in range(4):
                prog = self.progress.get(f"{filename}_part{i}", 0)
                print(f"\033[K{filename} part {i+1}.... {prog:.0f}%")

    def download_chunk(self, filename, chunk_id, chunk_size):
        """Download a specific chunk of a file using separate connection"""
        chunk_socket = None
        try:
            # Setup chunk connection
            chunk_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            chunk_socket.settimeout(30)
            chunk_socket.connect((HOST, PORT))
            
            # Skip initial file list
            _ = chunk_socket.recv(1024)
            
            # Request specific chunk
            chunk_socket.sendall(f"{filename}:{chunk_id}".encode())
            
            # Receive and save chunk data
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
        """Combine downloaded chunks into complete file"""
        with open(filename, 'wb') as outfile:
            for i in range(4):
                chunk_file = f"{filename}.part{i}"
                with open(chunk_file, 'rb') as infile:
                    outfile.write(infile.read())
                os.remove(chunk_file)

    def download_file(self, filename):
        """Download complete file using parallel chunks"""
        if filename in self.downloaded_files:
            return True

        try:
            # Get file size from server
            self.socket.sendall(filename.encode())
            filesize = int(self.socket.recv(1024).decode())
            self.socket.sendall(b"OK")
            
            # Setup chunk sizes and progress tracking
            self.progress = {}
            chunk_size = filesize // 4
            chunk_sizes = [chunk_size] * 3 + [filesize - (3 * chunk_size)]
            
            # Initialize progress display
            print('\n' * 4)
            
            # Start parallel chunk downloads
            threads = []
            for i in range(4):
                thread = threading.Thread(
                    target=self.download_chunk,
                    args=(filename, i, chunk_sizes[i])
                )
                thread.daemon = True
                thread.start()
                threads.append(thread)
            
            # Wait for all chunks to complete
            for thread in threads:
                thread.join()
            
            # Combine chunks and cleanup
            self.merge_chunks(filename)
            self.downloaded_files.add(filename)
            print(f"\nCompleted downloading {filename}")
            return True
            
        except Exception as e:
            print(f"\nError downloading {filename}: {e}")
            return False

    def start(self):
        """Main client loop"""
        while self.running:
            try:
                # Ensure valid server connection
                if not self.socket and not self.connect_to_server():
                    time.sleep(5)
                    continue

                if not self.check_connection():
                    self.socket = None  # Force reconnect
                    continue

                # Process new downloads
                new_files = self.check_new_downloads()
                for filename in new_files:
                    if not self.running:
                        break
                    
                    # Retry failed downloads
                    for attempt in range(3):
                        if self.download_file(filename):
                            break
                        print(f"Retry {attempt+1}/3 for {filename}")
                        time.sleep(1)
                
                # Wait before next check
                time.sleep(5)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
                self.socket = None
                time.sleep(5)

if __name__ == '__main__':
    client = FileClient()
    client.start()