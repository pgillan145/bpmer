# Bpmer

[Home](https://github.com/pgillan145/bpmer)

**Full Disclosure: This project was almost entirely coded by A.I.**

BPM data provided by [GetSongBPM.com](https://getsongbpm.com).

---


### Description

Scans Library.xml exported from Apple Music, attempts to pull data from the GetSongBPM API, then uses AppleScript to update the original Apple Music item.

### Setup
1. Get a GetSongBPM [API key](https://getsongbpm.com/api).

2. Export your library from Apple Music (File -> Library -> Export Library...) to Library.xml.

3. Update [config-sample.json](https://github.com/pgillan145/bpmer/blob/main/config-sample.json) to config.json and update it with the API key you collected in step 1, along with the name and location of the Library.xml file if you didn't save it to the bpmer directory.

4. Adjust the location of the  other cache and log files in config.json if you don't want them written in the current directory.


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
