# ntrip_proxy.py

A lightweight NTRIP TLS proxy that lets Mission Planner (and other NTRIP clients that don't support TLS) connect to modern HTTPS-only NTRIP casters.

**Co-authored by [Sui Jackson](https://github.com/YOUR_HANDLE) and [Claude.ai](https://claude.ai)**

---

## The Problem

Geoscience Australia's AUSCORS NTRIP caster (`ntrip.data.gnss.ga.gov.au`) moved to TLS-only on port 443. Mission Planner's built-in NTRIP client doesn't support TLS, so it throws a `Bad ntrip Response` error and RTK corrections stop working — even though your credentials and mountpoint are perfectly fine.

This is a known issue with Mission Planner ([GitHub #2295](https://github.com/ArduPilot/MissionPlanner/issues/2295), open since 2020, still unresolved).

---

## The Fix

`ntrip_proxy.py` sits between Mission Planner and the caster:

```
Mission Planner → localhost:2101 (plain HTTP) → ntrip_proxy.py → ntrip.data.gnss.ga.gov.au:443 (TLS)
```

It handles the TLS handshake and authentication, and re-serves the RTCM stream as plain HTTP NTRIP that Mission Planner can consume normally.

---

## Requirements

- Python 3.6+
- No external dependencies — stdlib only

---

## Installation

Just download `ntrip_proxy.py`. No pip install required.

---

## Usage

### Basic (Geoscience Australia / AUSCORS)

```bash
python ntrip_proxy.py --server ntrip.data.gnss.ga.gov.au --port 443 \
    --mountpoint YOUR_MOUNTPOINT --user YOUR_USERNAME --password YOUR_PASSWORD \
    --lat YOUR_LAT --lon YOUR_LON
```

Then in Mission Planner, connect NTRIP to:

```
http://localhost:2101/YOUR_MOUNTPOINT
```

No username or password needed in the Mission Planner URL — the proxy handles authentication.

### List available mountpoints

```bash
python ntrip_proxy.py --server ntrip.data.gnss.ga.gov.au --port 443 \
    --user YOUR_USERNAME --password YOUR_PASSWORD --list
```

### All options

| Argument | Default | Description |
|---|---|---|
| `--server` | *(required)* | Remote NTRIP caster hostname |
| `--port` | `443` | Remote caster port |
| `--mountpoint` | *(required)* | Mountpoint name |
| `--user` | *(required)* | NTRIP username |
| `--password` | *(required)* | NTRIP password |
| `--lat` | `0.0` | Your approximate latitude (for GGA) |
| `--lon` | `0.0` | Your approximate longitude (for GGA) |
| `--alt` | `0.0` | Your approximate altitude in metres |
| `--ggainterval` | `10` | How often to resend GGA to caster (seconds) |
| `--localport` | `2101` | Local port Mission Planner connects to |
| `--list` | — | Fetch sourcetable and exit |

---

## Finding Your Mountpoint

Log in to [gnss.ga.gov.au/stream](https://gnss.ga.gov.au/stream) to see which mountpoints your account has access to, or use `--list` to fetch the sourcetable directly.

For most users in Australia, a mountpoint close to your location will give the best RTK accuracy. Correction quality degrades roughly 1–1.5 cm per 10 km from the reference station.

---

## Works With Any TLS NTRIP Caster

Although written to solve the GA/AUSCORS problem, this proxy works with any NTRIP caster running over HTTPS. Just point `--server` and `--port` at your caster of choice.

---

## Running Automatically

If you want the proxy to start with Windows, create a batch file:

```bat
@echo off
python C:\path\to\ntrip_proxy.py --server ntrip.data.gnss.ga.gov.au --port 443 ^
    --mountpoint YOUR_MOUNTPOINT --user YOUR_USERNAME --password YOUR_PASSWORD ^
    --lat YOUR_LAT --lon YOUR_LON
```

Save it and add a shortcut to your Startup folder (`shell:startup` in Run).

---

## Background

This was developed in April 2026 after GA completed their migration to TLS-only NTRIP. Mission Planner users across Australia found their RTK setups silently broken with a cryptic `Bad ntrip Response` error that gave no indication the real cause was a TLS mismatch.

The proxy was written and tested in a single session with the help of [Claude.ai](https://claude.ai) (Anthropic). Pure stdlib, no dependencies, should keep working indefinitely.

---

## Licence

MIT — do what you like with it.
