"""Select a single browser playback stream; never fall back to desktop audio."""

import re

BROWSERS = re.compile(r"brave|chromium|chrome|vivaldi|firefox|msedge", re.I)


def matches_browser(app, browser=""):
    if not browser or browser.casefold() == "auto":
        return bool(BROWSERS.search(app))
    names = {"brave": r"\bbrave\b", "chromium": r"\bchromium\b",
             "chrome": r"\b(?:google-chrome|chrome)\b", "firefox": r"\bfirefox\b",
             "vivaldi": r"\bvivaldi\b", "edge": r"\b(?:msedge|microsoft edge)\b"}
    pattern = names.get(browser.casefold())
    return bool(pattern and re.search(pattern, app, re.I))


def select_stream(inputs, sinks, title="", browser=""):
    candidates = []
    for stream in inputs:
        props = stream.get("properties", {})
        app = " ".join(
            str(props.get(key, ""))
            for key in ("application.name", "application.process.binary", "application.id")
        )
        if not matches_browser(app, browser) or stream.get("corked") or stream.get("mute"):
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


def select_pipewire_stream(objects, title="", browser=""):
    candidates = []
    for node in objects:
        if node.get("type") != "PipeWire:Interface:Node":
            continue
        info = node.get("info") or {}
        props = info.get("props") or {}
        app = " ".join(str(props.get(key, "")) for key in
                       ("application.name", "application.process.binary", "application.id"))
        if (props.get("media.class") != "Stream/Output/Audio" or info.get("state") != "running"
                or not matches_browser(app, browser)):
            continue
        settings = info.get("params", {}).get("Props", [])
        if any(setting.get("mute") is True for setting in settings):
            continue
        serial = props.get("object.serial")
        if type(serial) is int and serial > 0:
            candidates.append(props)
    if len(candidates) > 1 and title:
        candidates = [p for p in candidates if title.casefold() in str(p.get("media.name", "")).casefold()]
    if len(candidates) != 1:
        return None
    return {"backend": "pipewire", "serial": candidates[0]["object.serial"]}


def capture_command(target):
    if target and target.get("backend") == "pipewire":
        serial = target.get("serial")
        if type(serial) is not int or serial <= 0:
            raise ValueError("No hay un nodo de navegador aislado")
        return ["pw-record", "--target", str(serial), "--properties",
                "{stream.capture.sink=true node.dont-fallback=true node.dont-reconnect=true}",
                "--rate", "16000", "--channels", "1", "--format", "s16", "--raw", "--latency", "40ms", "-"]
    return ["parec", *capture_args(target)]
