"""Run ShazamIO in its compatible runtime; bounded WAV bytes arrive on stdin."""
import asyncio
import json
import sys

from shazamio import Shazam


async def main():
    audio = sys.stdin.buffer.read(1_000_001)
    if not audio or len(audio) > 1_000_000:
        raise ValueError("Invalid audio window")
    result = await asyncio.wait_for(Shazam().recognize(audio), 22)
    print(json.dumps(result))


try:
    asyncio.run(main())
except Exception as error:
    print(json.dumps({"fatal": f"ShazamIO: {type(error).__name__}"}))
