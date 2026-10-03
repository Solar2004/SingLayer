"""Expose browser playback through standard MPRIS; no lyrics implementation here."""

import time

from dbus_fast import DBusError, Variant
from dbus_fast.constants import PropertyAccess
from dbus_fast.service import ServiceInterface, dbus_property, method, signal

BUS_NAME = "org.mpris.MediaPlayer2.singlayer"
OBJECT_PATH = "/org/mpris/MediaPlayer2"
NO_TRACK = OBJECT_PATH + "/TrackList/NoTrack"


class Root(ServiceInterface):
    def __init__(self):
        super().__init__("org.mpris.MediaPlayer2")

    @method()
    def Raise(self):
        pass

    @method()
    def Quit(self):
        pass

    @dbus_property(access=PropertyAccess.READ)
    def CanQuit(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def CanRaise(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def HasTrackList(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def Identity(self) -> "s":
        return "SingLayer · Browser music"

    @dbus_property(access=PropertyAccess.READ)
    def SupportedUriSchemes(self) -> "as":
        return []

    @dbus_property(access=PropertyAccess.READ)
    def SupportedMimeTypes(self) -> "as":
        return []


class MediaPlayer(ServiceInterface):
    def __init__(self, store, send_command):
        super().__init__("org.mpris.MediaPlayer2.Player")
        self.store = store
        self.send_command = send_command

    def capability(self, name):
        player = self.store.active()
        return bool(player and player.data.get(name))

    @dbus_property(access=PropertyAccess.READ)
    def PlaybackStatus(self) -> "s":
        player = self.store.active()
        return (
            {0: "Playing", 1: "Paused", 2: "Stopped"}.get(player.data.get("state"), "Stopped")
            if player
            else "Stopped"
        )

    @dbus_property(access=PropertyAccess.READ)
    def Metadata(self) -> "a{sv}":
        player = self.store.active()
        if not player:
            return {"mpris:trackid": Variant("o", NO_TRACK)}
        return {
            "mpris:trackid": Variant("o", player.track_id),
            "mpris:length": Variant("x", int(player.data.get("duration", 0) * 1_000_000)),
            "xesam:title": Variant("s", player.data.get("title", "")),
            "xesam:artist": Variant("as", [player.data.get("artist", "")]),
            "xesam:album": Variant("s", player.data.get("album", "")),
        }

    @dbus_property(access=PropertyAccess.READ)
    def Position(self) -> "x":
        player = self.store.active()
        return int(player.position(time.monotonic()) * 1_000_000) if player else 0

    @dbus_property(access=PropertyAccess.READ)
    def Rate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def MinimumRate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def MaximumRate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def CanControl(self) -> "b":
        return self.store.active() is not None

    @dbus_property(access=PropertyAccess.READ)
    def CanPlay(self) -> "b":
        return self.capability("canSetState")

    @dbus_property(access=PropertyAccess.READ)
    def CanPause(self) -> "b":
        return self.capability("canSetState")

    @dbus_property(access=PropertyAccess.READ)
    def CanSeek(self) -> "b":
        return self.capability("canSetPosition")

    @dbus_property(access=PropertyAccess.READ)
    def CanGoNext(self) -> "b":
        return self.capability("canSkipNext")

    @dbus_property(access=PropertyAccess.READ)
    def CanGoPrevious(self) -> "b":
        return self.capability("canSkipPrevious")

    @method()
    async def Play(self):
        await self.send_command(0, 0, "canSetState")

    @method()
    async def Pause(self):
        await self.send_command(0, 1, "canSetState")

    @method()
    async def PlayPause(self):
        await self.send_command(0, 1 if self.PlaybackStatus == "Playing" else 0, "canSetState")

    @method()
    async def Stop(self):
        await self.Pause()

    @method()
    async def Next(self):
        await self.send_command(2, 0, "canSkipNext")

    @method()
    async def Previous(self):
        await self.send_command(1, 0, "canSkipPrevious")

    @method()
    async def Seek(self, Offset: "x"):
        await self.send_command(3, max(0, (self.Position + Offset) / 1_000_000), "canSetPosition")

    @method()
    async def SetPosition(self, TrackId: "o", Position: "x"):
        player = self.store.active()
        if player and TrackId == player.track_id and Position >= 0:
            await self.send_command(3, Position / 1_000_000, "canSetPosition")

    @method()
    def OpenUri(self, Uri: "s"):
        raise DBusError("org.mpris.MediaPlayer2.NotSupported", "Open a song in your browser")

    @signal()
    def Seeked(self, position: "x") -> "x":
        return position

    def publish(self, seeked=False):
        self.emit_properties_changed(
            {
                "PlaybackStatus": self.PlaybackStatus,
                "Metadata": self.Metadata,
                "CanPlay": self.CanPlay,
                "CanPause": self.CanPause,
                "CanSeek": self.CanSeek,
                "CanGoNext": self.CanGoNext,
                "CanGoPrevious": self.CanGoPrevious,
                "CanControl": self.CanControl,
            }
        )
        if seeked:
            self.Seeked(self.Position)
