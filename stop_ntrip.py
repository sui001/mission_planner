#!/usr/bin/env python
"""Stop whatever is listening on the NTRIP proxy port.

Kills by port rather than by window title. Window-title matching does not work
reliably here: the process is python.exe, the title `start` assigns is not
always what ends up on the window, and a failed kill is silent, so the port
stays held and the next run cannot bind.

run_ntrip.py blocks on its child, so killing the listener makes the launcher
exit on its own. One kill is enough for both.

Usage:  python stop_ntrip.py [port]      (default 2101)
"""
import subprocess
import sys

port = sys.argv[1] if len(sys.argv) > 1 else "2101"

out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
pids = set()
for line in out.splitlines():
    parts = line.split()
    if len(parts) >= 5 and "LISTENING" in line and parts[1].endswith(":" + port):
        pids.add(parts[-1])

if not pids:
    print("nothing listening on %s" % port)
    raise SystemExit(0)

for pid in pids:
    r = subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, text=True)
    print("stopped pid %s on port %s" % (pid, port) if r.returncode == 0
          else "could not stop pid %s: %s" % (pid, r.stdout.strip() or r.stderr.strip()))
