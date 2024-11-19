import socket
import threading
import os
import time

# Configuration
HOST = '127.0.0.1'
PORT = 65432
INPUT_FILE = 'TCP_UDP_Data\\download_info.txt'
CHUNK_SIZE = 1024 * 1024  # 1MB

def download_chunk(filename, offset, chunk_size, part_num, progress):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.sendall(f'DOWNLOAD {filename} {offset} {chunk_size}'.encode())
        with open(f'{filename}.part{part_num}', 'wb') as f:
            while True:
                data = s.recv(1024)
                if not data:
                    break
                f.write(data)
                progress[part_num] += len(data)
                print(f'Downloading {filename} part {part_num} .... {progress[part_num] * 100 // chunk_size}%')

def download_file(filename):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.sendall('LIST'.encode())
        file_list = s.recv(1024).decode()
        file_size = None
        for line in file_list.split('\n'):
            if line.startswith(filename):
                file_size = int(line.split()[1].replace('MB', '')) * 1024 * 1024
                break
        if file_size is None:
            print(f'File {filename} not found on server.')
            return

    chunk_size = file_size // 4
    progress = [0] * 4
    threads = []
    for i in range(4):
        offset = i * chunk_size
        t = threading.Thread(target=download_chunk, args=(filename, offset, chunk_size, i, progress))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    with open(filename, 'wb') as f:
        for i in range(4):
            with open(f'{filename}.part{i}', 'rb') as part_file:
                f.write(part_file.read())
            os.remove(f'{filename}.part{i}')
    print(f'Download of {filename} completed.')

def monitor_input_file():
    downloaded_files = set()
    while True:
        with open(INPUT_FILE, 'r') as f:
            files_to_download = [line.strip() for line in f if line.strip() not in downloaded_files]
        for filename in files_to_download:
            download_file(filename)
            downloaded_files.add(filename)
        time.sleep(5)

if __name__ == '__main__':
    monitor_input_file()
