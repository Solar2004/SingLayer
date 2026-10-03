"""Normalize WebNowPlaying revision 3, preserving sparse updates and player identity."""

import hashlib
import math
import re
import time
from dataclasses import dataclass, field

FIELDS = (
    "id name title artist album cover state position duration volume rating repeat shuffle "
    "ratingSystem availableRepeat canSetState canSkipPrevious canSkipNext canSetPosition "
    "canSetVolume canSetRating canSetRepeat canSetShuffle createdAt updatedAt activeAt"
).split()
NUMBERS = set(FIELDS) - {"name", "title", "artist", "album", "cover"}


def decode_frame(message: str) -> tuple[int, str, dict]:
    """Empty fields mean unchanged; U+0001 means explicitly clear a string."""
    parts = message.split(" ", 2)
    kind = int(parts[0])
    if kind not in (0, 1, 2):
        return kind, "", {}
    if len(parts) < 2 or not parts[1].isdigit():
        raise ValueError("Missing numeric player ID")
    if kind == 2:
        return kind, parts[1], {}
    if len(parts) != 3:
        raise ValueError("Missing player data")
    values = re.split(r"(?<!\\)\|", parts[2])
    if len(values) != len(FIELDS) + 1 or values[-1] != "":
        raise ValueError("Invalid revision-3 field count")
    result = {}
    for key, value in zip(FIELDS, values):
        if not value:
            continue
        if key in NUMBERS:
            number = float(value)
            if not math.isfinite(number) or number < 0:
                raise ValueError("Invalid numeric field")
            if number > 2**53 or (key in {"position", "duration"} and number > 1_000_000_000):
                raise ValueError("Numeric field out of range")
            if key == "state" and number not in (0, 1, 2):
                raise ValueError("Invalid player state")
            result[key] = number
        else:
            result[key] = "" if value == "\x01" else value.replace(r"\|", "|")
    return kind, parts[1], result


@dataclass
class Player:
    connection: int
    browser_id: str
    data: dict = field(default_factory=dict)
    observed: float = field(default_factory=time.monotonic)
    position_observed: float = field(default_factory=time.monotonic)
    order: int = 0

    def position(self, now: float) -> float:
        # Stop extrapolating if a playing tab stops reporting its clock.
        elapsed = min(max(0.0, now - self.position_observed), 15.0)
        position = self.data.get("position", 0.0)
        if self.data.get("state", 2) == 0:
            position += elapsed
        duration = self.data.get("duration", 0.0)
        return min(position, duration) if duration > 0 else position

    @property
    def track_id(self) -> str:
        identity = "\0".join(str(self.data.get(k, "")) for k in ("title", "artist", "album", "duration"))
        digest = hashlib.sha256(identity.encode()).hexdigest()[:24]
        return f"/org/mpris/MediaPlayer2/track/t{self.connection}_{self.browser_id}_{digest}"


class PlayerStore:
    def __init__(self):
        self.players: dict[tuple[int, str], Player] = {}
        self.serial = 0

    def apply(self, connection: int, message: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        kind, browser_id, patch = decode_frame(message)
        key = connection, browser_id
        if kind == 2:
            self.players.pop(key, None)
            return
        if kind not in (0, 1):
            return
        if kind == 1 and key not in self.players:
            raise ValueError("Update before player added")
        player = self.players.get(key) if kind == 1 else None
        if player is None:
            player = Player(connection, browser_id, observed=now, position_observed=now)
        old_state = player.data.get("state", 2)
        track_changed = any(k in patch and patch[k] != player.data.get(k) for k in ("title", "artist"))
        if "position" not in patch and (track_changed or "state" in patch):
            patch["position"] = 0.0 if track_changed else player.position(now)
        if "position" in patch:
            player.position_observed = now
        if track_changed or (patch.get("state") == 0 and old_state != 0):
            self.serial += 1
            player.order = self.serial
        player.data.update(patch)
        player.observed = now
        self.players[key] = player

    def remove_connection(self, connection: int) -> None:
        self.players = {key: value for key, value in self.players.items() if key[0] != connection}

    def active(self) -> Player | None:
        candidates = [p for p in self.players.values() if p.data.get("title")]
        return max(candidates, key=lambda p: (p.data.get("state") == 0, p.order), default=None)
