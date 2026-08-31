#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import plistlib
from pathlib import Path
from typing import Iterator, TypedDict

LIBRARY_XML = Path("Library.xml")
COMPLETED_LOG = Path("completed.jsonl")


class Track(TypedDict):
    persistent_id: str
    name: str
    artist: str


def load_completed_ids(log_path: Path = COMPLETED_LOG) -> set[str]:
    if not log_path.exists():
        return set()
    ids = set()
    with log_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(json.loads(line)["persistent_id"])
    return ids


def mark_completed(persistent_id: str, bpm: int, log_path: Path = COMPLETED_LOG) -> None:
    entry = {
        "persistent_id": persistent_id,
        "bpm": bpm,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    with log_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def iter_pending_tracks(
    library_xml_path: Path = LIBRARY_XML,
    completed_ids: set[str] | None = None,
) -> Iterator[Track]:
    if completed_ids is None:
        completed_ids = load_completed_ids()

    with library_xml_path.open("rb") as f:
        library = plistlib.load(f)

    for track in library["Tracks"].values():
        persistent_id = track.get("Persistent ID")
        if not persistent_id or persistent_id in completed_ids:
            continue
        name = track.get("Name")
        artist = track.get("Artist")
        if not name or not artist:
            continue
        yield Track(persistent_id=persistent_id, name=name, artist=artist)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-y",
        dest="yes",
        action="store_true",
        help="process every pending track without confirming each one",
    )
    return parser.parse_args()


def confirm_process(track: Track) -> bool:
    prompt = f"Process {track['artist']} - {track['name']}? [Y/q] "
    while True:
        response = input(prompt).strip().lower()
        if response in ("", "y"):
            return True
        if response == "q":
            return False
        print("Enter to process, or q to quit.")


def main() -> None:
    args = parse_args()
    completed_ids = load_completed_ids()
    pending = list(iter_pending_tracks(completed_ids=completed_ids))
    print(f"{len(completed_ids)} already completed, {len(pending)} pending")

    for track in pending:
        if not args.yes and not confirm_process(track):
            print("Quitting.")
            break
        # TODO: look up tempo via getsongbpm.com, then apply it via AppleScript,
        # then mark_completed(track["persistent_id"], bpm) on success.
        print(f"  would process: {track['artist']} - {track['name']}  ({track['persistent_id']})")


if __name__ == "__main__":
    main()
