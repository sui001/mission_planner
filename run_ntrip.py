#!/usr/bin/env python
"""Start ntrip_proxy from a config file instead of the command line.

Credentials live in ~/.ntrip_grover.json, which sits outside every git repo on
this machine on purpose. Keeping them out of the argument list also keeps them
out of shell history and out of anything that lists running processes.

Usage:  python run_ntrip.py [path-to-config]
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
default_cfg = os.path.join(os.path.expanduser("~"), ".ntrip_grover.json")
cfg_path = sys.argv[1] if len(sys.argv) > 1 else default_cfg

if not os.path.exists(cfg_path):
    print("no config at %s" % cfg_path)
    print("Expected JSON with: server, port, mountpoint, user, password, lat, lon")
    raise SystemExit(1)

with open(cfg_path) as fh:
    c = json.load(fh)

cmd = [sys.executable, "-u", os.path.join(HERE, "ntrip_proxy.py"),
       "--server", str(c["server"]),
       "--port", str(c.get("port", 443)),
       "--mountpoint", str(c["mountpoint"]),
       "--user", str(c["user"]),
       "--password", str(c["password"]),
       "--lat", str(c.get("lat", 0.0)),
       "--lon", str(c.get("lon", 0.0)),
       "--localport", str(c.get("localport", 2101))]

# Echo everything except the credentials, so the log is safe to paste.
safe = list(cmd)
safe[safe.index("--password") + 1] = "********"
safe[safe.index("--user") + 1] = "********"
print("running: %s" % " ".join(safe[1:]))
sys.stdout.flush()
raise SystemExit(subprocess.call(cmd))
