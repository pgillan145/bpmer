# Bpmer

[Home](https://github.com/pgillan145/bpmer)

**Full Disclosure: This project was almost entirely coded by A.I.**

BPM data provided by [GetSongBPM.com](https://getsongbpm.com).

---


### Description

Scans Library.xml exported from Apple Music, attempts to pull data from the GetSongBPM API, then uses AppleScript to update the original Apple Music item.

### Usage
```bash

$ python ./bpmer.py
16 already completed, 7415 pending
Set Cream - Sunshine of Your Love to 117 BPM? [Y/q]
  done: Cream - Sunshine of Your Love  (70AC4A799F9158CF)  bpm=117
Looking up data for Daft Punk - The Son of Flynn
  SKIPPED (no BPM found): Daft Punk - The Son of Flynn
Looking up data for Billy Joel - My Life
Set Billy Joel - My Life to 129 BPM? [Y/q]

```
