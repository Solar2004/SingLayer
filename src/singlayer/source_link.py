"""Associate ephemeral browser source links with the active WNP recording."""
import math
import time
import unicodedata
from urllib.parse import urlsplit


def normalize_title(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def source_message(value):
    url = value['url']
    parsed = urlsplit(url)
    host = parsed.hostname
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('Invalid source URL')
    if host in ('soundcloud.com', 'www.soundcloud.com'):
        parts = parsed.path.strip('/').split('/')
        if len(parts) != 2 or parts[0] in ('you', 'discover', 'search', 'charts', 'tags', 'settings'):
            raise ValueError('Not a recording URL')
    elif host in ('youtube.com', 'www.youtube.com', 'music.youtube.com'):
        if parsed.path != '/watch' or not parsed.query.startswith('v='):
            raise ValueError('Not a recording URL')
    else:
        raise ValueError('Unsupported automatic source')
    title, duration = value['title'], value['duration']
    if not isinstance(title, str) or not title.strip() or len(title) > 1000:
        raise ValueError('Invalid source title')
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 0 < duration <= 900:
        raise ValueError('Invalid source duration')
    return {'url': url, 'title': normalize_title(title), 'duration': duration, 'at': time.monotonic()}


def matching_source(entries, player):
    if not player:
        return None
    duration = player.data.get('duration', 0)
    title = normalize_title(player.data.get('title', ''))
    urls = {entry['url'] for entry in entries if time.monotonic() - entry['at'] < 8
            and title == entry['title'] and abs(duration - entry['duration']) <= 1.5}
    return next(iter(urls)) if len(urls) == 1 else None
