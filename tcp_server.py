import socket
import threading
import os

# Configuration
HOST = '127.0.0.1'
PORT = 65432
FILE_LIST = 'TCP_UDP_Data\\download_info.txt'

def handle_client(conn, addr):
    print(f'Connected by {addr}')
    while True:
        data = conn.recv(1024).decode()
        if not data:
            break
        
        parts = data.split(maxsplit=1)
        command = parts[0]
        
        if command == 'LIST':
            with open(FILE_LIST, 'r') as f:
                file_list = f.read()
            conn.sendall(file_list.encode())
        elif command == 'DOWNLOAD':
            if len(parts) < 2:
                print(f'Invalid command from {addr}: {data}')
                continue
            try:
                filename, offset, chunk_size = parts[1].rsplit(' ', 2)
                offset = int(offset)
                chunk_size = int(chunk_size)
            except ValueError:
                print(f'Invalid command from {addr}: {data}')
                continue
            
            try:
                with open(filename, 'rb') as f:
                    f.seek(offset)
                    chunk = f.read(chunk_size)
                conn.sendall(chunk)
            except FileNotFoundError:
                print(f'File not found: {filename}')
                conn.sendall(b'')
    conn.close()

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f'Server listening on {HOST}:{PORT}')
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr)).start()

if __name__ == '__main__':
    start_server()
