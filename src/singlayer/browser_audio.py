"""Select a single browser playback stream; never fall back to desktop audio."""

import re

BROWSERS = re.compile(r"brave|chromium|chrome|vivaldi|firefox|msedge", re.I)


def select_stream(inputs, sinks, title=""):
    candidates = []
    for stream in inputs:
        props = stream.get("properties", {})
        app = " ".join(
            str(props.get(key, ""))
            for key in ("application.name", "application.process.binary", "application.id")
        )
        if not BROWSERS.search(app) or stream.get("corked") or stream.get("mute"):
            continue
        candidates.append(stream)
    # Multiple audible tabs/apps are ambiguous. Only an explicit media title resolves it.
    if len(candidates) > 1 and title:
        candidates = [
            s
            for s in candidates
            if title.casefold() in str(s.get("properties", {}).get("media.name", "")).casefold()
        ]
    if len(candidates) != 1:
        return None
    stream = candidates[0]
    sink = next((s for s in sinks if s.get("index") == stream.get("sink")), None)
    device = (sink.get("monitor_source_name") or sink.get("monitor_source")) if sink else None
    if not isinstance(device, str) or not device:
        return None
    return {"index": int(stream["index"]), "device": device}


def capture_args(target):
    if not target or not isinstance(target.get("index"), int) or not target.get("device"):
        raise ValueError("No hay un flujo de navegador aislado")
    return [
        f"--device={target['device']}",
        f"--monitor-stream={target['index']}",
        "--format=s16le",
        "--rate=16000",
        "--channels=1",
        "--latency-msec=40",
        "--process-time-msec=20",
    ]
