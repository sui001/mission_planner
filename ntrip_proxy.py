#!/usr/bin/env python3
"""
ntrip_proxy.py - NTRIP TLS Proxy

Connects to a TLS/HTTPS NTRIP caster and re-serves the stream as plain
HTTP NTRIP locally, so clients that don't support TLS (e.g. Mission Planner)
can connect.

Developed to work around Geoscience Australia's AUSCORS caster moving to
TLS-only (port 443), which broke Mission Planner's built-in NTRIP client.
Should work with any TLS NTRIP caster.

Usage examples:

  # Geoscience Australia (AUSCORS)
  python ntrip_proxy.py --server ntrip.data.gnss.ga.gov.au --port 443 \\
      --mountpoint YOUR_MOUNTPOINT --user YOU --password YOURPASS \\
      --lat -35.28 --lon 149.13

  # Then point Mission Planner at:
  #   http://localhost:2101/YOUR_MOUNTPOINT

  # Custom local port
  python ntrip_proxy.py --server ntrip.data.gnss.ga.gov.au --port 443 \\
      --mountpoint YOUR_MOUNTPOINT --user YOU --password YOURPASS \\
      --lat -35.28 --lon 149.13 --localport 2102

  # List available mountpoints
  python ntrip_proxy.py --server ntrip.data.gnss.ga.gov.au --port 443 \\
      --user YOU --password YOURPASS --list

Requirements: Python 3.6+ (stdlib only, no pip installs needed)
"""

import argparse
import base64
import socket
import ssl
import sys
import threading
import time


def make_gga(lat, lon, alt):
    """Build a minimal NMEA GGA sentence."""
    lat_deg = int(abs(lat))
    lat_min = (abs(lat) - lat_deg) * 60
    lon_deg = int(abs(lon))
    lon_min = (abs(lon) - lon_deg) * 60
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    t = time.strftime("%H%M%S.00", time.gmtime())
    body = (
        f"GPGGA,{t},"
        f"{lat_deg:02d}{lat_min:07.4f},{ns},"
        f"{lon_deg:03d}{lon_min:07.4f},{ew},"
        f"1,08,1.0,{alt:.1f},M,0.0,M,,"
    )
    cksum = 0
    for c in body:
        cksum ^= ord(c)
    return f"${body}*{cksum:02X}\r\n"


def fetch_sourcetable(server, port, user, password):
    """Fetch and print the caster sourcetable, then exit."""
    credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
    request = (
        f"GET / HTTP/1.0\r\n"
        f"Host: {server}\r\n"
        f"Ntrip-Version: Ntrip/2.0\r\n"
        f"User-Agent: NTRIP PythonProxy/1.0\r\n"
        f"Authorization: Basic {credentials}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    raw = socket.create_connection((server, port), timeout=15)
    ctx = ssl.create_default_context()
    tls = ctx.wrap_socket(raw, server_hostname=server)
    tls.sendall(request.encode())

    response = b""
    while True:
        chunk = tls.recv(4096)
        if not chunk:
            break
        response += chunk

    tls.close()
    print(response.decode(errors="replace"))


def connect_to_caster(server, port, mountpoint, user, password):
    """Open TLS connection to remote NTRIP caster, return (socket, leftover_bytes)."""
    credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
    request = (
        f"GET /{mountpoint} HTTP/1.0\r\n"
        f"Host: {server}\r\n"
        f"Ntrip-Version: Ntrip/2.0\r\n"
        f"User-Agent: NTRIP PythonProxy/1.0\r\n"
        f"Authorization: Basic {credentials}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    raw = socket.create_connection((server, port), timeout=15)
    ctx = ssl.create_default_context()
    tls = ctx.wrap_socket(raw, server_hostname=server)
    tls.sendall(request.encode())

    response = b""
    while b"\r\n\r\n" not in response:
        chunk = tls.recv(1024)
        if not chunk:
            raise ConnectionError("Caster closed connection during handshake")
        response += chunk

    header, _, leftover = response.partition(b"\r\n\r\n")
    header_str = header.decode(errors="replace")
    status_line = header_str.splitlines()[0]
    print(f"[proxy] Caster response: {status_line}")

    if "200" not in header_str and "ICY" not in header_str:
        raise ConnectionError(f"Caster rejected connection:\n{header_str}")

    return tls, leftover


def handle_client(client_sock, client_addr, args):
    """Handle one NTRIP client connection (e.g. Mission Planner)."""
    print(f"[proxy] Client connected from {client_addr}")
    try:
        # Read client request
        req = b""
        client_sock.settimeout(5)
        try:
            while b"\r\n\r\n" not in req:
                chunk = client_sock.recv(1024)
                if not chunk:
                    break
                req += chunk
        except socket.timeout:
            pass

        first_line = req.decode(errors="replace").splitlines()[0] if req else "(empty)"
        print(f"[proxy] Client requested: {first_line}")

        # Send NTRIP OK response
        client_sock.sendall(
            b"ICY 200 OK\r\n"
            b"Content-Type: gnss/data\r\n"
            b"\r\n"
        )

        # Connect to remote caster
        print(f"[proxy] Connecting to {args.server}:{args.port}/{args.mountpoint} ...")
        caster_sock, leftover = connect_to_caster(
            args.server, args.port, args.mountpoint, args.user, args.password
        )
        print("[proxy] Connected. Streaming RTCM data...")

        # Send initial GGA position
        if args.lat != 0.0 or args.lon != 0.0:
            gga = make_gga(args.lat, args.lon, args.alt)
            caster_sock.sendall(gga.encode())
            print(f"[proxy] Sent GGA: {gga.strip()}")

        last_gga = time.time()
        total_bytes = 0

        if leftover:
            client_sock.sendall(leftover)
            total_bytes += len(leftover)

        caster_sock.settimeout(15)
        client_sock.settimeout(15)

        while True:
            # Periodic GGA updates
            if (args.lat != 0.0 or args.lon != 0.0) and (time.time() - last_gga > args.ggainterval):
                gga = make_gga(args.lat, args.lon, args.alt)
                caster_sock.sendall(gga.encode())
                last_gga = time.time()

            try:
                data = caster_sock.recv(4096)
            except socket.timeout:
                print("[proxy] Caster timeout")
                break

            if not data:
                print("[proxy] Caster closed connection")
                break

            try:
                client_sock.sendall(data)
                total_bytes += len(data)
                if total_bytes % 10000 < len(data):
                    print(f"[proxy] {total_bytes:,} bytes relayed")
            except (BrokenPipeError, ConnectionResetError, OSError):
                print("[proxy] Client disconnected")
                break

        caster_sock.close()

    except Exception as e:
        print(f"[proxy] Error: {e}")
    finally:
        client_sock.close()
        print(f"[proxy] Client {client_addr} done")


def main():
    parser = argparse.ArgumentParser(
        description="NTRIP TLS Proxy - relay a TLS NTRIP caster as plain HTTP for clients like Mission Planner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--server",      required=True,           help="Remote NTRIP caster hostname")
    parser.add_argument("--port",        type=int, default=443,   help="Remote caster port (default: 443)")
    parser.add_argument("--mountpoint",  default="",              help="Mountpoint name (omit with --list)")
    parser.add_argument("--user",        required=True,           help="NTRIP username")
    parser.add_argument("--password",    required=True,           help="NTRIP password")
    parser.add_argument("--lat",         type=float, default=0.0, help="Approximate latitude for GGA (e.g. -35.28)")
    parser.add_argument("--lon",         type=float, default=0.0, help="Approximate longitude for GGA (e.g. 149.13)")
    parser.add_argument("--alt",         type=float, default=0.0, help="Approximate altitude in metres (default: 0)")
    parser.add_argument("--ggainterval", type=int,   default=10,  help="GGA resend interval in seconds (default: 10)")
    parser.add_argument("--localport",   type=int,   default=2101,help="Local port to listen on (default: 2101)")
    parser.add_argument("--list",        action="store_true",     help="Fetch and print sourcetable then exit")

    args = parser.parse_args()

    if args.list:
        fetch_sourcetable(args.server, args.port, args.user, args.password)
        sys.exit(0)

    if not args.mountpoint:
        parser.error("--mountpoint is required unless using --list")

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("0.0.0.0", args.localport))
    server_sock.listen(5)

    print("[proxy] NTRIP TLS Proxy")
    print(f"[proxy] Remote : {args.server}:{args.port}/{args.mountpoint}")
    print(f"[proxy] Local  : http://localhost:{args.localport}/{args.mountpoint}")
    print(f"[proxy] Point Mission Planner at: http://localhost:{args.localport}/{args.mountpoint}")
    print("[proxy] Ctrl+C to stop\n")

    try:
        while True:
            client_sock, client_addr = server_sock.accept()
            t = threading.Thread(
                target=handle_client,
                args=(client_sock, client_addr, args),
                daemon=True,
            )
            t.start()
    except KeyboardInterrupt:
        print("\n[proxy] Stopped")
    finally:
        server_sock.close()


if __name__ == "__main__":
    main()
