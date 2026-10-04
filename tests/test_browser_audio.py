from singlayer.artwork import safe_cover_url
from singlayer.browser_audio import capture_args, select_stream


def stream(index, name, title="Demo", **kw):
    return {"index": index, "sink": 1, "properties": {"application.name": name, "media.name": title}, **kw}


def test_select_browser_not_desktop_or_other_app():
    sinks = [{"index": 1, "monitor_source_name": "speaker.monitor"}]
    selected = select_stream([stream(2, "Brave"), stream(3, "Music player")], sinks)
    assert selected == {"index": 2, "device": "speaker.monitor"}
    args = capture_args(selected)
    assert "--monitor-stream=2" in args
    assert "--latency-msec=40" in args
    assert not any("DEFAULT" in a for a in args)
    assert select_stream([stream(2, "Brave", corked=True)], sinks) is None
    assert select_stream([stream(2, "Music player")], sinks) is None
    assert select_stream([stream(2, "Brave"), stream(3, "Firefox")], sinks) is None
    assert select_stream([stream(2, "Brave"), stream(3, "Firefox", "Other")], sinks, "Demo")["index"] == 2


def test_artwork_rejects_private_arbitrary_and_credential_urls():
    assert safe_cover_url("https://i1.sndcdn.com/artworks-demo.jpg")
    for url in (
        "http://i1.sndcdn.com/a",
        "https://localhost/a",
        "file:///tmp/a",
        "https://i1.sndcdn.com.evil.test/a",
        "https://user@i1.sndcdn.com/a",
        "https://i1.sndcdn.com:8443/a",
    ):
        assert safe_cover_url(url) is None


def test_real_pactl_monitor_source_key():
    sinks = [{"index": 1, "monitor_source": "alsa_output.example.monitor"}]
    assert select_stream([stream(7, "Brave")], sinks) == {"index": 7, "device": "alsa_output.example.monitor"}
