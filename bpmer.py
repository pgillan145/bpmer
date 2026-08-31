#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import plistlib
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterator, TypedDict

CONFIG_FILE = Path("config.json")
GETSONGBPM_SEARCH_URL = "https://api.getsong.co/search/"


class Track(TypedDict):
    persistent_id: str
    name: str
    artist: str
    bpm: int


class Config(TypedDict):
    library_xml: Path
    completed_log: Path
    lookup_cache: Path
    getsongbpm_api_key: str


def load_config(config_path: Path = CONFIG_FILE) -> Config:
    with config_path.open() as f:
        raw = json.load(f)
    return Config(
        library_xml=Path(raw["library_xml"]),
        completed_log=Path(raw["completed_log"]),
        lookup_cache=Path(raw["lookup_cache"]),
        getsongbpm_api_key=raw["getsongbpm_api_key"],
    )


def load_completed_ids(log_path: Path) -> set[str]:
    if not log_path.exists():
        return set()
    ids = set()
    with log_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(json.loads(line)["persistent_id"])
    return ids


def mark_completed(track: Track, bpm: int, log_path: Path) -> None:
    entry = {
        "persistent_id": track["persistent_id"],
        "artist": track["artist"],
        "name": track["name"],
        "bpm": bpm,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    with log_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def iter_pending_tracks(
    library_xml_path: Path,
    completed_ids: set[str],
) -> Iterator[Track]:
    with library_xml_path.open("rb") as f:
        library = plistlib.load(f)

    for track in library["Tracks"].values():
        persistent_id = track.get("Persistent ID")
        if not persistent_id or persistent_id in completed_ids:
            continue
        name = track.get("Name")
        artist = track.get("Artist")
        bpm = track.get("BPM")
        if not name or not artist or bpm:
            continue
        yield Track(persistent_id=persistent_id, name=name, artist=artist, bpm=bpm)


def load_lookup_cache(cache_path: Path) -> dict[str, dict | None]:
    """Map persistent_id -> the GetSongBPM match previously found for it (or None for no match).

    This only ever holds real answers from GetSongBPM, never failed lookups —
    a network/API error should still be retried on the next run.
    """
    cache: dict[str, dict | None] = {}
    if not cache_path.exists():
        return cache
    with cache_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                entry = json.loads(line)
                cache[entry["persistent_id"]] = entry["match"]
    return cache


def cache_lookup(persistent_id: str, match: dict | None, cache_path: Path) -> None:
    entry = {"persistent_id": persistent_id, "match": match}
    with cache_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


class GetSongBPMError(Exception):
    """A GetSongBPM lookup failed outright (as opposed to finding no match)."""


class GetSongBPMAuthError(GetSongBPMError):
    """GetSongBPM rejected the request in a way that will affect every other lookup too."""


def lookup_track_info(track: Track, api_key: str) -> dict | None:
    """Return GetSongBPM's full best-match record, or None if it has no match.

    The record includes tempo, time_sig, key_of, open_key, danceability,
    acousticness, plus nested artist/album objects — see
    https://getsongbpm.com/api for the shape. Only tempo currently has a
    home in Music.app (bpm); the full record is cached in lookup_cache.jsonl
    in case a use for the rest of it turns up later.

    Raises GetSongBPMError (or the more specific GetSongBPMAuthError) if the
    lookup itself failed, so callers can tell "no data for this song" apart
    from "we don't actually know, try again".
    """
    lookup = f"song:{track['name']} artist:{track['artist']}"
    query = urllib.parse.urlencode({"api_key": api_key, "type": "both", "lookup": lookup})
    url = f"{GETSONGBPM_SEARCH_URL}?{query}"

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise GetSongBPMAuthError(
                f"GetSongBPM request rejected (HTTP {e.code}) — likely a bad API key or a "
                "block on this endpoint; every other lookup would fail the same way"
            ) from e
        raise GetSongBPMError(f"GetSongBPM returned HTTP {e.code}") from e
    except OSError as e:
        # covers URLError, timeouts, DNS failures, connection resets, etc.
        raise GetSongBPMError(f"network error contacting GetSongBPM: {e}") from e

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise GetSongBPMError(f"GetSongBPM returned a response that wasn't JSON: {e}") from e

    results = data.get("search")
    if isinstance(results, dict):
        # documented "no match" shape: {"search": {"error": "no result"}}
        return None
    if not isinstance(results, list):
        raise GetSongBPMError(f"unexpected GetSongBPM response shape: {data!r}")
    if not results:
        return None

    return results[0]


PERSISTENT_ID_RE = re.compile(r"[0-9A-Fa-f]+")


class AppleScriptError(Exception):
    """Writing bpm for this track failed (as opposed to a systemic automation problem)."""


class AppleScriptFatalError(AppleScriptError):
    """AppleScript automation itself isn't usable — retrying other tracks won't help."""


def set_bpm_via_applescript(persistent_id: str, bpm: int) -> None:
    if not PERSISTENT_ID_RE.fullmatch(persistent_id):
        raise AppleScriptError(f"refusing to run AppleScript with unexpected persistent ID: {persistent_id!r}")

    script = (
        'tell application "Music"\n'
        f'    set bpm of (first track whose persistent ID is "{persistent_id}") to {bpm}\n'
        "end tell\n"
    )
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode == 0:
        return
    time.sleep(0.75)

    message = result.stderr.strip() or f"osascript exited with status {result.returncode}"
    if "-1743" in message or "not authorized" in message.lower():
        raise AppleScriptFatalError(
            "Music automation isn't authorized for this terminal/app — grant it in "
            f"System Settings > Privacy & Security > Automation: {message}"
        )
    raise AppleScriptError(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-y",
        dest="yes",
        action="store_true",
        help="process every pending track without confirming each one",
    )
    return parser.parse_args()


def confirm_process(track: Track, bpm: int) -> bool:
    prompt = f"Set {track['artist']} - {track['name']} to {bpm} BPM? [Y/q] "
    while True:
        response = input(prompt).strip().lower()
        if response in ("", "y"):
            return True
        if response == "q":
            return False
        print("Enter to process, or q to quit.")


def main() -> None:
    args = parse_args()
    config = load_config()
    api_key = config["getsongbpm_api_key"]
    completed_ids = load_completed_ids(config["completed_log"])
    lookup_cache = load_lookup_cache(config["lookup_cache"])
    pending = list(iter_pending_tracks(config["library_xml"], completed_ids))
    print(f"{len(completed_ids)} already completed, {len(pending)} pending")

    for track in pending:
        persistent_id = track["persistent_id"]
        if persistent_id in lookup_cache:
            match = lookup_cache[persistent_id]
        else:
            print(f"Looking up data for {track['artist']} - {track['name']}")
            try:
                match = lookup_track_info(track, api_key)
            except GetSongBPMAuthError as e:
                print(f"FATAL: {e}")
                break
            except GetSongBPMError as e:
                print(f"  SKIPPED (lookup failed): {track['artist']} - {track['name']}: {e}")
                continue
            cache_lookup(persistent_id, match, config["lookup_cache"])
            lookup_cache[persistent_id] = match

        tempo = match.get("tempo") if match else None
        if tempo is None:
            print(f"  SKIPPED (no BPM found): {track['artist']} - {track['name']}")
            continue
        try:
            bpm = round(float(tempo))
        except (TypeError, ValueError):
            print(f"  SKIPPED (unexpected tempo value {tempo!r}): {track['artist']} - {track['name']}")
            continue

        if not args.yes and not confirm_process(track, bpm):
            print("Quitting.")
            break
        try:
            set_bpm_via_applescript(track["persistent_id"], bpm)
        except AppleScriptFatalError as e:
            print(f"FATAL: {e}")
            break
        except AppleScriptError as e:
            print(f"  SKIPPED (AppleScript failed): {track['artist']} - {track['name']}: {e}")
            continue

        mark_completed(track, bpm, config["completed_log"])
        print(f"  done: {track['artist']} - {track['name']}  ({track['persistent_id']})  bpm={bpm}")


if __name__ == "__main__":
    main()
