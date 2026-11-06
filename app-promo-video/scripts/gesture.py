"""Plays a continuous touch gesture on the phone (press, move along a path, lift), for scenes a
Maestro swipe cannot show: Maestro only swipes in straight lines, while a joystick-like control
(an arc picker from a corner button) is shown best by sweeping arcs at several distances.

A gesture file (JSON, next to the Maestro flows):
    {
      "anchor": [135, 2070],      the control's centre on the screen, in px
      "radius": 691,              the reach the shares below refer to, in px
      "corner": "bottom_left",    bottom_left: angle 0 is straight up and 1 is towards the right;
                                  bottom_right: 0 straight up and 1 towards the left
      "hz": 45,                   touch events per second
      "strokes": [                each one: finger down on the anchor, the path, finger up
        {"hold_ms": 350,
         "path": [[angle, share, ms], ...],   to that point (angle 0..1, share of the radius) in ms,
                                              eased in and out
         "pause_after_ms": 1200}
      ]
    }

Or a list of quick taps and swipes, for screens Maestro cannot drive at a natural pace (a ticking
timer, like a REC clock, never lets the screen settle, so Maestro waits seconds before every tap):
    {"steps": [{"tap": [540, 1700], "after_ms": 350},
               {"swipe": [300, 900, 700, 1100, 600], "after_ms": 400},   x1 y1 x2 y2 duration_ms
               {"wait_ms": 1500}]}
Positions in px of the recording phone (read them from `adb shell uiautomator dump`: Compose
testTags appear as resource-id when the app exposes them).

Used by capture.py when a scene has "gesture": the flow prepares the screen, then the gesture plays,
all while recording. Can also be run alone: python gesture.py <gesture.json> [--device SERIAL]
"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import adb_path, fail  # noqa: E402


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * t)


def point(spec, angle, share):
    ax, ay = spec["anchor"]
    r = spec["radius"] * share
    theta = angle * math.pi / 2
    dx = math.sin(theta) * r
    if spec.get("corner", "bottom_left") == "bottom_right":
        dx = -dx
    return round(ax + dx), round(ay - math.cos(theta) * r)


def steps_script(spec):
    """Quick taps and swipes ("steps"), each followed by its pause."""
    lines = []
    for step in spec["steps"]:
        if "tap" in step:
            x, y = step["tap"]
            lines.append(f"input tap {x} {y}")
        elif "swipe" in step:
            x1, y1, x2, y2, ms = step["swipe"]
            lines.append(f"input swipe {x1} {y1} {x2} {y2} {ms}")
        wait = step.get("after_ms", step.get("wait_ms", 0))
        if wait:
            lines.append(f"sleep {wait / 1000:.3f}")
    return "\n".join(lines) + "\n"


def script(spec):
    """The shell commands of the gesture: motion events with short sleeps between them."""
    if "steps" in spec:
        return steps_script(spec)
    hz = spec.get("hz", 45)
    step = 1.0 / hz
    lines = []
    for stroke in spec["strokes"]:
        ax, ay = spec["anchor"]
        lines.append(f"input motionevent DOWN {ax} {ay}")
        lines.append(f"sleep {stroke.get('hold_ms', 300) / 1000:.3f}")
        angle, share = 0.0, 0.0
        for target_angle, target_share, ms in stroke["path"]:
            n = max(1, round(ms / 1000 * hz))
            for i in range(1, n + 1):
                t = ease(i / n)
                x, y = point(spec, angle + (target_angle - angle) * t, share + (target_share - share) * t)
                lines.append(f"input motionevent MOVE {x} {y}")
                lines.append(f"sleep {step * 0.5:.3f}")  # the input command itself takes about half a step
            angle, share = target_angle, target_share
        x, y = point(spec, angle, share)
        lines.append(f"sleep {stroke.get('release_hold_ms', 150) / 1000:.3f}")
        lines.append(f"input motionevent UP {x} {y}")
        lines.append(f"sleep {stroke.get('pause_after_ms', 1000) / 1000:.3f}")
    return "\n".join(lines) + "\n"


def play(adb, serial, gesture_file):
    spec = json.loads(Path(gesture_file).read_text(encoding="utf-8"))
    commands = script(spec)
    # One shell session reading the commands from stdin: no process per event on the PC side.
    result = subprocess.run([adb, "-s", serial, "shell", "sh"], input=commands, text=True,
                            capture_output=True, timeout=300)
    if result.returncode != 0:
        fail(f"Gesture failed: {result.stderr[-500:]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("gesture")
    parser.add_argument("--device", default="")
    args = parser.parse_args()
    adb = adb_path()
    serial = args.device
    if not serial:
        lines = subprocess.run([adb, "devices"], capture_output=True, text=True).stdout.splitlines()[1:]
        devices = [l.split("\t")[0] for l in lines if l.endswith("\tdevice")]
        if len(devices) != 1:
            fail("Connect one phone or use --device")
        serial = devices[0]
    play(adb, serial, args.gesture)


if __name__ == "__main__":
    main()
