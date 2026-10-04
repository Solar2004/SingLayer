"""Allow only known public music image CDNs; never fetch arbitrary player URLs."""

from urllib.parse import urlsplit


def safe_cover_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        url = urlsplit(value)
        if url.scheme != "https" or url.port not in (None, 443) or url.username or url.password:
            return None
        if url.hostname not in {"i1.sndcdn.com", "i2.sndcdn.com", "i.scdn.co", "i.ytimg.com"}:
            return None
        return value
    except ValueError:
        return None
