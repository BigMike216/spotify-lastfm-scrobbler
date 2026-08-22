#!/usr/bin/env python3
import json
import sys
import os
import glob
import time
import shutil
from json.decoder import JSONDecodeError

# Config
MIN_MS_PLAYED = 30000         # Only include plays >= 30 seconds (30,000 ms)
OUTPUT_DIR = 'MusicCSV'       # Output folder for part files
LINES_PER_FILE = 650          # Rows per part file


def csv_quote(value: str) -> str:
    """Quote a value for CSV output."""
    return '"' + str(value).replace('"', '""') + '"'


def iter_json_values(text):
    """Iteratively decode multiple top-level JSON values from a single string."""
    dec = json.JSONDecoder()
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        try:
            obj, end = dec.raw_decode(text, i)
        except JSONDecodeError:
            next_candidates = [x for x in (
                text.find('{', i+1), text.find('[', i+1)) if x != -1]
            if not next_candidates:
                break
            i = min(next_candidates)
            continue
        i = end
        yield obj


def iter_history_items(path):
    """Yield individual history items from a JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = f.read()

        for val in iter_json_values(data):
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        yield item
            elif isinstance(val, dict):
                yield val
    except Exception:
        return


def _first_nonempty(d: dict, keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return None


def extract_info(item):
    """Extract (artist, track, album) from a history item."""
    artist = _first_nonempty(item, [
        'master_metadata_album_artist_name',
        'artistName',
        'artist',
    ])
    track = _first_nonempty(item, [
        'master_metadata_track_name',
        'trackName',
        'track',
        'song',
    ])
    album = _first_nonempty(item, [
        'master_metadata_album_album_name',
        'albumName',
        'album',
    ])

    if artist and track:
        return str(artist), str(track), str(album) if album else ""
    return None


def extract_duration_ms(item):
    """Best-effort extraction of play duration in ms."""
    for k in ('ms_played', 'msPlayed', 'playback_duration_ms', 'playbackDurationMs', 'duration_ms'):
        if k in item and item[k] is not None:
            try:
                return int(item[k])
            except (TypeError, ValueError):
                pass
    return None


def find_spotify_history_files():
    """Find Spotify history JSON files in the current directory."""
    patterns = [
        'StreamingHistory_music_*.json',
        'StreamingHistory*.json',
        'Streaming_History_Audio_*.json',
        'Streaming_History_*.json',
        'endsong_*.json',
        '*History*.json',
    ]

    found_files = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            found_files.extend(matches)

    if not found_files:
        json_files = [f for f in glob.glob('*.json') if os.path.isfile(f)]
        found_files = json_files

    seen = set()
    unique_files = []
    for f in found_files:
        if f not in seen and os.path.isfile(f):
            seen.add(f)
            unique_files.append(f)

    return sorted(unique_files)


def process_json_directly_to_parts(files, lines_per_file):
    """Read JSON history files and write directly into MusicCSV/partN.csv files."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total_rows = 0
    part_idx = 0
    cur_rows = 0
    outfile = None
    cur_name = None

    for path in files:
        try:
            for item in iter_history_items(path):
                info = extract_info(item)
                if not info:
                    continue

                duration = extract_duration_ms(item)
                if duration is not None and duration < MIN_MS_PLAYED:
                    continue

                # Start a new part file if needed
                if cur_rows % lines_per_file == 0:
                    if outfile:
                        outfile.close()
                        print(f"✅ Created >~< {cur_name} ({cur_rows} rows)")

                    cur_name = os.path.join(OUTPUT_DIR, f"part{part_idx}.csv")
                    outfile = open(cur_name, "w", newline='', encoding="utf-8")
                    part_idx += 1
                    cur_rows = 0

                artist, track, album = info
                outfile.write(
                    f'{csv_quote(artist)}, {csv_quote(track)}, {csv_quote(album)}\n')
                cur_rows += 1
                total_rows += 1

        except Exception:
            continue

    if outfile:
        outfile.close()
        print(f"✅ Created >~< {cur_name} ({cur_rows} rows)")

    return total_rows, part_idx


def cleanup_json_files(files):
    """Ask user how to handle original JSON files after conversion."""
    print("\n🧹 CLEANUP OPTION:")
    print("1. Move JSON files to 'processed_jsons/' folder (Recommended)")
    print("2. Delete JSON files")
    print("3. Keep them in current folder")

    choice = input("\nEnter choice (1-3): ").strip()

    if choice == '1':
        dest_folder = "processed_jsons"
        os.makedirs(dest_folder, exist_ok=True)
        for f in files:
            shutil.move(f, os.path.join(dest_folder, os.path.basename(f)))
        print(f"📦 Moved {len(files)} JSON files to '{dest_folder}/'")

    elif choice == '2':
        confirm = input(
            "⚠️ Are you sure you want to permanently delete the JSON files? (yes/no): ").lower()
        if confirm == 'yes':
            for f in files:
                os.remove(f)
            print(f"🗑️ Deleted {len(files)} JSON files.")
        else:
            print("Operation cancelled. Files kept.")

    else:
        print("Files kept in current folder!")


def main(argv):
    print("Converting Spotify JSON to MusicCSV parts...hehe")
    start_time = time.perf_counter()

    files = argv if argv else find_spotify_history_files()

    if not files:
        print("❌ No JSON files found in current directory :<")
        sys.exit(1)

    total_rows, total_parts = process_json_directly_to_parts(
        files, LINES_PER_FILE)
    elapsed = time.perf_counter() - start_time

    if total_rows > 0:
        print(
            f"\nRAAAAAAHHHH!! Done {total_rows} tracks split into {total_parts} files in '{OUTPUT_DIR}/' ({elapsed:.1f}s)")
        cleanup_json_files(files)
    else:
        print(f"\n❌ No valid tracks found to convert :< ({elapsed:.1f}s)")


if __name__ == '__main__':
    main(sys.argv[1:])
