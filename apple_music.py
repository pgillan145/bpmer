#!/usr/bin/env python3
"""
Minimal Apple Music API client: generates a MusicKit developer token (JWT)
and hits the catalog search endpoint.

Setup (one time, in Apple Developer portal -> Certificates, IDs & Profiles -> Keys):
  1. Create a key with the "MusicKit" capability enabled. Download the .p8 file
     (you only get to download it once).
  2. Note the Key ID (shown next to the key) and your Team ID (top right of the
     portal, under your account name).

Usage:
  export APPLE_TEAM_ID=ABCDE12345
  export APPLE_KEY_ID=XYZ98765
  export APPLE_KEY_PATH=/path/to/AuthKey_XYZ98765.p8
  ./venv/bin/python apple_music.py "radiohead"
"""
import os
import sys
import time

import jwt
import requests

TEAM_ID = os.environ.get("APPLE_TEAM_ID")
KEY_ID = os.environ.get("APPLE_KEY_ID")
KEY_PATH = os.environ.get("APPLE_KEY_PATH")


def make_developer_token() -> str:
    missing = [n for n, v in [("APPLE_TEAM_ID", TEAM_ID), ("APPLE_KEY_ID", KEY_ID), ("APPLE_KEY_PATH", KEY_PATH)] if not v]
    if missing:
        sys.exit(f"Missing env var(s): {', '.join(missing)}")

    with open(KEY_PATH) as f:
        private_key = f.read()

    now = int(time.time())
    return jwt.encode(
        {"iss": TEAM_ID, "iat": now, "exp": now + 60 * 60 * 24 * 180},  # 180 days, max allowed is ~6 months
        private_key,
        algorithm="ES256",
        headers={"kid": KEY_ID},
    )


def search(term: str, storefront: str = "us", types: str = "songs"):
    token = make_developer_token()
    resp = requests.get(
        f"https://api.music.apple.com/v1/catalog/{storefront}/search",
        params={"term": term, "types": types, "limit": 5},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"Usage: {sys.argv[0]} <search term>")
    data = search(sys.argv[1])
    for song in data.get("results", {}).get("songs", {}).get("data", []):
        attrs = song["attributes"]
        print(f"{attrs['artistName']} - {attrs['name']}  ({attrs.get('albumName')})")
