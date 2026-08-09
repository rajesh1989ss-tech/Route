#!/usr/bin/env python3
"""
nmea-bridge.py — puts a WiFi AIS transponder within reach of a web browser.

A browser cannot open a raw TCP or UDP socket, so it cannot talk to an AIS
transponder directly. This bridge reads the transponder's NMEA stream and
re-serves it as a WebSocket, which a browser can read. It also serves the
Rhumb files sitting next to it, so the whole thing runs from one command
with nothing installed — Python 3.7 or newer and the standard library only.

    python3 nmea-bridge.py --tcp 192.168.1.1:39150
    python3 nmea-bridge.py --udp 10110
    python3 nmea-bridge.py --tcp 192.168.4.1:2000 --port 8080

Then open  http://localhost:8080/  on the machine running this, or
http://<this-machine-ip>:8080/ from a tablet on the same WiFi, and in
Rhumb set the AIS source to  ws://<same-host>:8080/nmea

  --tcp HOST:PORT   connect to the transponder as a TCP client (most units)
  --udp PORT        listen for UDP broadcasts on this port (some units)
  --port N          HTTP/WebSocket port to serve on (default 8080)
  --dir PATH        folder to serve (default: the folder this file is in)
  --echo            print every sentence received, for troubleshooting
"""

import argparse, base64, hashlib, os, socket, struct, sys, threading, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

WS_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

clients = set()
clients_lock = threading.Lock()
recent = []                      # last few sentences, replayed to a browser that joins late
stats = {"lines": 0, "since": time.time(), "source": "not connected"}


def broadcast(line: str):
    stats["lines"] += 1
    recent.append(line)
    if len(recent) > 400:
        del recent[:100]
    frame = ws_frame(line.encode("utf-8", "replace"))
    dead = []
    with clients_lock:
        for c in clients:
            try:
                c.sendall(frame)
            except Exception:
                dead.append(c)
        for c in dead:
            clients.discard(c)
            try:
                c.close()
            except Exception:
                pass


def ws_frame(payload: bytes, opcode: int = 0x1) -> bytes:
    """Server-to-client frame: never masked."""
    head = bytes([0x80 | opcode])
    n = len(payload)
    if n < 126:
        head += bytes([n])
    elif n < (1 << 16):
        head += bytes([126]) + struct.pack(">H", n)
    else:
        head += bytes([127]) + struct.pack(">Q", n)
    return head + payload


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.split("?")[0] == "/nmea":
            return self.websocket()
        if self.path.split("?")[0] == "/status":
            body = ('{"source":"%s","lines":%d,"clients":%d,"uptime":%d}'
                    % (stats["source"], stats["lines"], len(clients),
                       int(time.time() - stats["since"]))).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return SimpleHTTPRequestHandler.do_GET(self)

    def websocket(self):
        key = self.headers.get("Sec-WebSocket-Key")
        if not key or "websocket" not in (self.headers.get("Upgrade") or "").lower():
            self.send_error(400, "expected a WebSocket upgrade")
            return
        accept = base64.b64encode(
            hashlib.sha1(key.encode() + WS_GUID).digest()).decode()
        self.wfile.write(("HTTP/1.1 101 Switching Protocols\r\n"
                          "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                          "Sec-WebSocket-Accept: %s\r\n\r\n" % accept).encode())
        self.wfile.flush()
        sock = self.connection
        with clients_lock:
            clients.add(sock)
        print("  browser connected (%d now listening)" % len(clients))
        try:
            sock.sendall(ws_frame(b"$PRHUM,BRIDGE,connected*00"))
            for line in list(recent):        # give the new browser the current picture
                sock.sendall(ws_frame(line.encode("utf-8", "replace")))
            while True:                       # drain client frames; handle close/ping
                hdr = sock.recv(2)
                if not hdr or len(hdr) < 2:
                    break
                op = hdr[0] & 0x0F
                ln = hdr[1] & 0x7F
                masked = hdr[1] & 0x80
                if ln == 126:
                    ln = struct.unpack(">H", sock.recv(2))[0]
                elif ln == 127:
                    ln = struct.unpack(">Q", sock.recv(8))[0]
                mask = sock.recv(4) if masked else b""
                data = b""
                while len(data) < ln:
                    chunk = sock.recv(ln - len(data))
                    if not chunk:
                        break
                    data += chunk
                if masked:
                    data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
                if op == 0x8:
                    break
                if op == 0x9:
                    sock.sendall(ws_frame(data, 0xA))
        except Exception:
            pass
        finally:
            with clients_lock:
                clients.discard(sock)
            print("  browser disconnected (%d still listening)" % len(clients))


def reader_tcp(host, port, echo):
    while True:
        try:
            stats["source"] = "connecting to %s:%d" % (host, port)
            print("connecting to %s:%d …" % (host, port))
            s = socket.create_connection((host, port), timeout=10)
            s.settimeout(None)
            stats["source"] = "tcp %s:%d" % (host, port)
            print("connected to the transponder")
            buf = b""
            while True:
                data = s.recv(4096)
                if not data:
                    raise ConnectionError("stream ended")
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.decode("ascii", "replace").strip()
                    if line:
                        if echo:
                            print(" <", line)
                        broadcast(line)
        except Exception as e:
            stats["source"] = "reconnecting (%s)" % e
            print("lost the transponder (%s) — retrying in 5 s" % e)
            time.sleep(5)


def reader_udp(port, echo):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except Exception:
        pass
    s.bind(("", port))
    stats["source"] = "udp :%d" % port
    print("listening for UDP broadcasts on port %d" % port)
    while True:
        data, _ = s.recvfrom(4096)
        for line in data.decode("ascii", "replace").splitlines():
            line = line.strip()
            if line:
                if echo:
                    print(" <", line)
                broadcast(line)


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--tcp", help="HOST:PORT of the transponder")
    ap.add_argument("--udp", type=int, help="UDP port to listen on")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--dir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--echo", action="store_true")
    a = ap.parse_args()
    if not a.tcp and not a.udp:
        ap.error("give either --tcp HOST:PORT or --udp PORT")

    os.chdir(a.dir)
    if a.tcp:
        host, _, port = a.tcp.partition(":")
        t = threading.Thread(target=reader_tcp, args=(host, int(port or 39150), a.echo), daemon=True)
    else:
        t = threading.Thread(target=reader_udp, args=(a.udp, a.echo), daemon=True)
    t.start()

    srv = ThreadingHTTPServer(("", a.port), Handler)
    ip = lan_ip()
    print("\n  Rhumb          http://%s:%d/" % (ip, a.port))
    print("  AIS source     ws://%s:%d/nmea" % (ip, a.port))
    print("  on this machine use http://localhost:%d/ — GPS and install work there\n" % a.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
