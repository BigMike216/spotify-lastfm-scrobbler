#!/usr/bin/env python3
import pylast
import time
import os
import sys
import glob
import re
from datetime import datetime
from dotenv import load_dotenv
import json
import csv

# Load environment variables
load_dotenv()


class LastFMScrobbler:
    def __init__(self):
        """Initialize Last.fm connection"""
        try:
            # Get credentials from .env file
            API_KEY = os.getenv('LASTFM_API_KEY')
            API_SECRET = os.getenv('LASTFM_API_SECRET')
            USERNAME = os.getenv('LASTFM_USERNAME')
            PASSWORD = os.getenv('LASTFM_PASSWORD')

            if not all([API_KEY, API_SECRET, USERNAME, PASSWORD]):
                raise ValueError("Missing credentials in .env file!")

            # Generate password hash
            password_hash = pylast.md5(PASSWORD)

            # Create network object
            self.network = pylast.LastFMNetwork(
                api_key=API_KEY,
                api_secret=API_SECRET,
                username=USERNAME,
                password_hash=password_hash
            )

            print(f"✅ Connected to Last.fm as {USERNAME} yayy^^")

        except Exception as e:
            print(f"❌ Failed to connect to Last.fm: {e} :<")
            sys.exit(1)

    def list_part_indices(self, directory="MusicCSV"):
        """Return sorted list of available part indices from MusicCSV/part*.csv"""
        files = glob.glob(os.path.join(directory, "part*.csv"))
        indices = []
        for p in files:
            m = re.match(r"^part(\d+)\.csv$", os.path.basename(p))
            if m:
                indices.append(int(m.group(1)))
        return sorted(indices)

    def read_csv_file(self, filepath):
        """Read CSV file (supports 2 columns OR 3 columns with album)"""
        songs = []
        problematic_lines = []

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
                csv_reader = csv.reader(
                    file, quotechar='"', skipinitialspace=True)

                for line_num, row in enumerate(csv_reader, 1):
                    try:
                        if len(row) >= 2:
                            artist = row[0].strip().strip('"').strip()
                            track = row[1].strip().strip('"').strip()
                            album = row[2].strip().strip(
                                '"').strip() if len(row) >= 3 else ""

                            # Skip headers
                            if artist and track and not (
                                artist.lower() == "artist" and track.lower() in ("track", "title")
                            ):
                                songs.append({
                                    'artist': artist,
                                    'track': track,
                                    'album': album if album else None
                                })
                    except Exception as e:
                        problematic_lines.append({
                            'line': line_num,
                            'content': str(row),
                            'error': str(e)
                        })
                        continue

            print(
                f"📁 Successfully loaded {len(songs)} songs from {filepath} ^^")
            return songs

        except FileNotFoundError:
            print(f"❌ File not found: {filepath}")
            return []
        except Exception as e:
            print(f"❌ Error reading file {filepath}: {e}")
            return []

    def scrobble_batch(self, songs_batch, batch_num, total_batches):
        """Scrobble a batch of songs (max 50) including album if available"""
        try:
            current_time = int(time.time())

            scrobbles = []
            for i, song in enumerate(songs_batch):
                # Stagger timestamps back by 30 seconds each so Last.fm treats them in sequence
                timestamp = current_time - (i * 30)

                scrobble_data = {
                    'artist': song['artist'],
                    'title': song['track'],
                    'timestamp': timestamp
                }

                # Include album only if it exists in the CSV
                if song.get('album'):
                    scrobble_data['album'] = song['album']

                scrobbles.append(scrobble_data)

            # Scrobble the batch
            self.network.scrobble_many(scrobbles)

            print(
                f"✅ Batch {batch_num}/{total_batches} scrobbled successfully ({len(songs_batch)} songs)")
            return True

        except Exception as e:
            print(f"❌ Error scrobbling batch {batch_num}: {e}")
            print("🔄 Attempting individual scrobbles...")
            return self.scrobble_individually(songs_batch, batch_num)

    def scrobble_individually(self, songs_batch, batch_num):
        """Fallback method to scrobble songs one by one"""
        success_count = 0
        current_time = int(time.time())

        for i, song in enumerate(songs_batch):
            try:
                timestamp = current_time - (i * 30)

                kwargs = {
                    'artist': song['artist'],
                    'title': song['track'],
                    'timestamp': timestamp
                }
                if song.get('album'):
                    kwargs['album'] = song['album']

                self.network.scrobble(**kwargs)
                success_count += 1
                print(f"  ✓ Scrobbled: {song['artist']} - {song['track']}")
                time.sleep(0.5)
            except Exception as e:
                print(f"  ✗ Failed: {song['artist']} - {song['track']} ({e})")

        print(
            f"📊 Batch {batch_num}: {success_count}/{len(songs_batch)} songs scrobbled individually")
        return success_count > 0

    def process_file(self, file_number):
        """Process a single CSV file"""
        filepath = f"MusicCSV/part{file_number}.csv"

        if not os.path.exists(filepath):
            print(f"❌ File not found: {filepath}")
            return False

        print(f"\n{'='*50}")
        print(f"📂 Processing: {filepath}")
        print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}\n")

        songs = self.read_csv_file(filepath)

        if not songs:
            print("❌ No songs to scrobble!")
            return False

        print("\n📋 Sample of songs to be scrobbled:")
        print("-" * 50)
        for i, song in enumerate(songs[:5]):
            album_str = f" [{song['album']}]" if song.get('album') else ""
            print(f"{i+1}. {song['artist']} - {song['track']}{album_str}")
        if len(songs) > 5:
            print(f"... and {len(songs) - 5} more songs")
        print("-" * 50)

        batch_size = 50
        total_batches = (len(songs) + batch_size - 1) // batch_size
        successful_batches = 0
        failed_songs = []

        print(f"\n📊 Total songs: {len(songs)}")
        print(f"📦 Total batches: {total_batches} (up to 50 songs each)\n")

        confirm = input("Do you want to proceed? (yes/no): ").lower()
        if confirm != 'yes':
            print("❌ Cancelled by user")
            return False

        print("\n🚀 Starting scrobbling process...\n")

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(songs))
            batch = songs[start_idx:end_idx]

            print(f"Processing songs {start_idx + 1} to {end_idx}...")

            success = self.scrobble_batch(batch, batch_num + 1, total_batches)

            if success:
                successful_batches += 1
            else:
                failed_songs.extend(batch)

            if batch_num < total_batches - 1:
                print("⏳ Waiting 3 seconds before next batch...")
                time.sleep(3)

        print(f"\n{'='*50}")
        print("📊 SUMMARY")
        print(f"{'='*50}")
        print(f"✅ Successful batches: {successful_batches}/{total_batches}")

        if failed_songs:
            failed_file = f"failed_songs_part{file_number}.json"
            with open(failed_file, 'w') as f:
                json.dump(failed_songs, f, indent=2)
            print(f"💾 Failed songs saved to: {failed_file}  bwaaa")

        self.save_progress(file_number)
        return True

    def save_progress(self, file_number):
        """Save progress"""
        progress_file = "scrobble_progress.json"
        try:
            if os.path.exists(progress_file):
                with open(progress_file, 'r') as f:
                    progress = json.load(f)
            else:
                progress = {'completed': [], 'last_run': {}}

            if file_number not in progress['completed']:
                progress['completed'].append(file_number)

            progress['last_run'] = {
                'file': f"part{file_number}.csv",
                'date': datetime.now().isoformat(),
                'timestamp': int(time.time())
            }

            with open(progress_file, 'w') as f:
                json.dump(progress, f, indent=2)

        except Exception as e:
            print(f"⚠️ Could not save progress: {e}  bwaaa")

    def check_progress(self):
        """Check progress status"""
        progress_file = "scrobble_progress.json"
        available = self.list_part_indices()

        if os.path.exists(progress_file):
            with open(progress_file, 'r') as f:
                progress = json.load(f)
        else:
            progress = {'completed': [], 'last_run': {}}

        completed = sorted(set(progress.get('completed', [])))
        remaining = [i for i in available if i not in completed]

        print("\n📊 PROGRESS STATUS:")
        print(f"{'='*50}")
        print(f"Available files: {[f'part{i}.csv' for i in available]}")
        print(f"Completed files: {completed}")
        if remaining:
            print(
                f"Remaining files: {', '.join([f'part{i}.csv' for i in remaining])}")
        else:
            print("All files completed!")
        print(f"{'='*50}\n")

        return completed


def main():
    print("""
    ╔════════════════════════════════════════════╗
    ║   Last.fm Scrobbler v3.0 by BIG MIKE :3    ║
    ╚════════════════════════════════════════════╝
    """)

    scrobbler = LastFMScrobbler()
    available = scrobbler.list_part_indices()

    if not available:
        print("❌ No part*.csv files found in MusicCSV/ o~O")
        return

    completed = scrobbler.check_progress()
    remaining = [i for i in available if i not in completed]

    if not remaining:
        print("✅ All files have been processed hehe :p")
        return

    next_file = remaining[0]

    print(f"📌 Next file to process: part{next_file}.csv")
    print("\nOptions:")
    print("1. Process next file automatically")
    print("2. Choose a specific file")
    print("3. Check a CSV file for issues")
    print("4. Exit")

    choice = input("\nEnter your choice (1-4): ")

    if choice == '1':
        scrobbler.process_file(next_file)
    elif choice == '2':
        nums_list = ", ".join(str(i) for i in available)
        try:
            file_num = int(input(f"Enter file number ({nums_list}): "))
        except ValueError:
            print("❌ Invalid number sillyy!")
            return
        if file_num in available:
            scrobbler.process_file(file_num)
        else:
            print("❌ Invalid file number sillyy!")
    elif choice == '3':
        nums_list = ", ".join(str(i) for i in available)
        try:
            file_num = int(
                input(f"Enter file number to check ({nums_list}): "))
        except ValueError:
            print("❌ Invalid number sillyy!")
            return
        if file_num in available:
            filepath = f"MusicCSV/part{file_num}.csv"
            songs = scrobbler.read_csv_file(filepath)
            if songs:
                print(
                    f"\n✅ File is readable! Contains {len(songs)} valid songs")
                print("\nFirst 10 songs:")
                for i, song in enumerate(songs[:10], 1):
                    album_str = f" [{song['album']}]" if song.get(
                        'album') else ""
                    print(
                        f"{i}. {song['artist']} - {song['track']}{album_str}")
        else:
            print("❌ Invalid file number!")
    elif choice == '4':
        print("👋 cyaaaa > <")


if __name__ == "__main__":
    main()
