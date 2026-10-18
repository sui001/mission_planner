# ntrip_proxy.py

> **Archived 19 Oct 2026.** This still works as it stands, and stays here to
> read and use. Development has moved into a private project repo, so this
> copy will not get further changes.

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

**Mind the naming.** Every GA mountpoint is a four-letter station code followed
by `00AUS0`, so Gungahlin is `GNGN00AUS0`, not `GNGNAUS0`. Dropping the `00` is
easy and the symptom is unhelpful: the caster accepts the connection, returns
`ICY 200 OK`, then closes it without sending a byte. That reads as a broken
proxy rather than a typo.

`--list` is the fastest way to settle it. The sourcetable also carries each
station's latitude and longitude, so it can be sorted by distance from you.
Correction quality drops roughly 1 to 1.5 cm per 10 km, so the nearest
mountpoint is usually the right one.

For most users in Australia, a mountpoint close to your location will give the best RTK accuracy. Correction quality degrades roughly 1–1.5 cm per 10 km from the reference station.

---

## Works With Any TLS NTRIP Caster

Although written to solve the GA/AUSCORS problem, this proxy works with any NTRIP caster running over HTTPS. Just point `--server` and `--port` at your caster of choice.

---

## start_grover.bat: one click for RTK plus Mission Planner

`start_grover.bat` starts the proxy, waits until it is actually listening, then
launches Mission Planner, and stops the proxy again when Mission Planner
closes.

The waiting matters. The proxy has to be up **before** Mission Planner tries to
connect, or the NTRIP box fails and has to be reconnected by hand. The batch
polls for the port rather than guessing at a sleep, and after about 15 seconds
gives up and starts Mission Planner anyway, so a caster outage does not stop
you flying without RTK.

Edit the three paths at the top for your machine: `PYTHON`, `MP` and `CONFIG`.
Credentials are not in the batch file, they come from the JSON that
`run_ntrip.py` reads.

Two things learned making it work, in case you adapt it:

- **Do not use `timeout` to wait.** It fails outright with "Input redirection
  is not supported" whenever stdin is not a console, which includes shortcuts
  and schedulers. `ping -n 2 127.0.0.1 >nul` works everywhere.
- **Do not kill the proxy by window title.** The process is `python.exe`, the
  title given to `start` is not reliably what ends up on the window, and a
  failed `taskkill` is silent, so the port stays held and the next run cannot
  bind. `stop_ntrip.py` kills by port instead, which is exact.

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

## gps_status.py

Reads the live GPS solution off the autopilot and says how good it is, without
needing Mission Planner connected. Useful because "is RTK working" is a
different question from "are corrections flowing", and the proxy can be
perfectly healthy while the answer is still no.

```
python gps_status.py COM40
```

The number that matters is the fix type:

| Fix type | Meaning | Rough accuracy |
|---|---|---|
| 3 | 3D fix | metres |
| 4 | DGPS | under a metre |
| 5 | RTK Float | decimetres |
| 6 | RTK Fixed | centimetres |

Float means corrections are arriving but carrier-phase ambiguities are not
resolved yet. It normally reaches Fixed within a minute or two under open sky.
Sitting on Float indefinitely is the signal worth chasing.

**This cannot be tested indoors.** With no sky view the fix type is 1 and the
satellite count is 0, which looks identical to corrections not arriving. Take
it outside before concluding anything.

Needs `pymavlink`. Note that only one program can hold the serial port, so
disconnect Mission Planner first.

## Licence

MIT — do what you like with it.
