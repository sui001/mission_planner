"""What is the GPS actually doing right now, and how good is it?"""
import sys, time
from pymavlink import mavutil

FIX = {0: "no GPS", 1: "no fix", 2: "2D fix", 3: "3D fix",
       4: "DGPS", 5: "RTK Float", 6: "RTK Fixed",
       7: "static", 8: "PPP"}

m = mavutil.mavlink_connection(sys.argv[1] if len(sys.argv) > 1 else "COM40",
                               baud=115200)
if m.wait_heartbeat(timeout=10) is None:
    print("no heartbeat"); sys.exit(1)
m.mav.request_data_stream_send(m.target_system, m.target_component,
                               mavutil.mavlink.MAV_DATA_STREAM_ALL, 5, 1)

best = None
rtcm = 0
t0 = time.time()
while time.time() - t0 < 15:
    msg = m.recv_match(blocking=True, timeout=1)
    if msg is None:
        continue
    t = msg.get_type()
    if t == "GPS_RAW_INT":
        best = msg
    elif t == "GPS_RTCM_DATA":
        rtcm += 1

if best is None:
    print("no GPS_RAW_INT seen"); sys.exit(1)

print("fix type      %d  (%s)" % (best.fix_type, FIX.get(best.fix_type, "?")))
print("satellites    %d" % best.satellites_visible)
print("HDOP          %.2f" % (best.eph / 100.0) if best.eph not in (0, 65535) else "HDOP          unknown")
for label, attr, unit in (("horiz accuracy", "h_acc", "mm"),
                          ("vert accuracy", "v_acc", "mm")):
    v = getattr(best, attr, None)
    if v:
        print("%-13s %.2f m  (%d %s)" % (label, v / 1000.0, v, unit))
    else:
        print("%-13s not reported by this GPS" % label)
print("RTCM packets seen on the link in 15s: %d" % rtcm)
print()
if best.fix_type >= 6:
    print("RTK Fixed. This is the centimetre-level solution.")
elif best.fix_type == 5:
    print("RTK Float. Corrections are arriving but ambiguities are not resolved")
    print("yet, so expect decimetres rather than centimetres. Usually converges")
    print("in a minute or two with a clear sky view.")
else:
    print("Not an RTK solution. Corrections are either not arriving or not")
    print("being applied. Check Mission Planner's NTRIP box is connected.")
