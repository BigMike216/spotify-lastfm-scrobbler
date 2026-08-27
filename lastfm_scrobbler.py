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
import hashlib
import requests
import xml.etree.ElementTree as ET


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

            self.username = USERNAME

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
        """Read CSV file with feedback on why lines are skipped"""

        songs = []
        line_num = 0

        try:
            with open(
                filepath,
                'r',
                encoding='utf-8',
                errors='replace'
            ) as file:

                csv_reader = csv.reader(
                    file,
                    quotechar='"',
                    skipinitialspace=True
                )

                for line_num, row in enumerate(csv_reader, 1):

                    # Skip completely empty rows
                    if not row or len([x for x in row if x.strip()]) == 0:
                        print(
                            f"ℹ️ Line {line_num}: Skipped empty line."
                        )
                        continue

                    # Skip rows with missing columns
                    if len(row) < 2:
                        print(
                            f"⚠️ Line {line_num}: "
                            f"Skipped due to missing columns "
                            f"(found {len(row)}, need at least 2). "
                            f"Row data: {row}"
                        )
                        continue

                    artist = row[0].strip()
                    track = row[1].strip()
                    album = row[2].strip() if len(row) >= 3 else ""

                    # Skip header
                    if (
                        artist.lower() == "artist"
                        and track.lower() in ("track", "title")
                    ):
                        print(
                            f"ℹ️ Line {line_num}: Skipped header row."
                        )
                        continue

                    # Missing artist or track
                    if not artist or not track:
                        print(
                            f"⚠️ Line {line_num}: "
                            f"Skipped because artist or track "
                            f"name is blank. Row data: {row}"
                        )
                        continue

                    songs.append({
                        'artist': artist,
                        'track': track,
                        'album': album if album else None
                    })

            print(
                f"📁 Loaded {len(songs)} valid songs "
                f"out of {line_num} total lines from {filepath} ^^"
            )

            return songs

        except FileNotFoundError:
            print(f"❌ File not found: {filepath}")
            return []

        except Exception as e:
            print(f"❌ Error reading file {filepath}: {e}")
            return []

    def make_signature(self, params):
        """
        Create Last.fm API signature.
        """

        signature_string = ""

        for key in sorted(params.keys()):
            signature_string += key + str(params[key])

        signature_string += self.network.api_secret

        return hashlib.md5(
            signature_string.encode('utf-8')
        ).hexdigest()

    def get_recent_scrobbles(self, limit=200):

        try:
            params = {
                'method': 'user.getrecenttracks',
                'user': self.username,
                'api_key': self.network.api_key,
                'limit': limit,
                'format': 'json'
            }

            response = requests.get(
                'https://ws.audioscrobbler.com/2.0/',
                params=params,
                timeout=30
            )

            response.raise_for_status()

            data = response.json()

            tracks = data.get('recenttracks', {}).get('track', [])

            recent = set()

            for t in tracks:
                # Skip "now playing" entries (no date)
                if '@attr' in t and t['@attr'].get('nowplaying') == 'true':
                    continue

                date_info = t.get('date', {})
                uts = date_info.get('uts')

                if uts is None:
                    continue

                artist_name = t.get('artist', {}).get(
                    '#text', '').lower().strip()
                track_name = t.get('name', '').lower().strip()

                recent.add((artist_name, track_name, int(uts)))

            return recent

        except Exception as e:
            print(f"⚠️ Could not fetch recent scrobbles: {e}")
            return None

    def scrobble_batch(
        self,
        songs_batch,
        batch_num,
        total_batches,
        timestamps_batch
    ):
        """
        Send one batch directly to Last.fm and inspect
        accepted/ignored results for EVERY song.
        """

        params = {
            'method': 'track.scrobble',
            'api_key': self.network.api_key,
            'sk': self.network.session_key
        }

        # Add songs
        for i, song in enumerate(songs_batch):

            params[f'artist[{i}]'] = song['artist']
            params[f'track[{i}]'] = song['track']
            params[f'timestamp[{i}]'] = timestamps_batch[i]

            if song.get('album'):
                params[f'album[{i}]'] = song['album']

        # Generate API signature
        params['api_sig'] = self.make_signature(params)

        print(
            f"\n📡 Sending batch {batch_num}/{total_batches} "
            f"({len(songs_batch)} songs)..."
        )

        try:

            response = requests.post(
                'https://ws.audioscrobbler.com/2.0/',
                data=params,
                timeout=30
            )

            print(f"🌐 HTTP status: {response.status_code}")

            response.raise_for_status()

            # Parse XML response
            root = ET.fromstring(response.text)

            status = root.attrib.get('status')

            if status != 'ok':

                error = root.find('error')

                if error is not None:
                    code = error.attrib.get('code')
                    message = error.text

                    raise Exception(
                        f"Last.fm API error {code}: {message}"
                    )

                raise Exception(
                    f"Last.fm returned status={status}"
                )

            scrobbles_element = root.find('scrobbles')

            if scrobbles_element is None:
                raise Exception(
                    "Last.fm response contained no <scrobbles> element."
                )

            accepted = int(
                scrobbles_element.attrib.get('accepted', '0')
            )

            ignored = int(
                scrobbles_element.attrib.get('ignored', '0')
            )

            print(
                f"📊 Last.fm response: "
                f"accepted={accepted}, ignored={ignored}"
            )

            failed_songs = []

            response_scrobbles = scrobbles_element.findall('scrobble')

            # Inspect EVERY returned scrobble
            for i, scrobble in enumerate(response_scrobbles):

                ignored_message = scrobble.find('ignoredMessage')

                ignored_code = 0
                ignored_text = ""

                if ignored_message is not None:

                    ignored_code = int(
                        ignored_message.attrib.get('code', '0')
                    )

                    ignored_text = (ignored_message.text or "").strip()

                if ignored_code != 0:

                    song = songs_batch[i]

                    print(f"\n❌ Last.fm IGNORED:")
                    print(f"   Song: {song['artist']} - {song['track']}")
                    print(f"   Code: {ignored_code}")
                    print(
                        f"   Reason: "
                        f"{self.get_ignore_reason(ignored_code)}"
                    )

                    if ignored_text:
                        print(f"   Message: {ignored_text}")

                    failed_songs.append({
                        'artist': song['artist'],
                        'track': song['track'],
                        'album': song.get('album'),
                        'ignored_code': ignored_code,
                        'ignored_reason':
                            self.get_ignore_reason(ignored_code),
                        'ignored_message': ignored_text
                    })

            # Safety check
            expected = len(songs_batch)

            if len(response_scrobbles) != expected:

                print(f"\n⚠️ WARNING:")
                print(f"   Sent: {expected}")
                print(
                    f"   Response contained: "
                    f"{len(response_scrobbles)}"
                )
                print(
                    "   Raw Last.fm response saved "
                    "for investigation."
                )

                with open(
                    f"lastfm_response_batch{batch_num}.xml",
                    'w',
                    encoding='utf-8'
                ) as f:
                    f.write(response.text)

            # Strong consistency check
            if accepted + ignored != expected:

                print(f"\n⚠️ RESPONSE COUNT MISMATCH!")
                print(f"   Sent: {expected}")
                print(f"   Accepted: {accepted}")
                print(f"   Ignored: {ignored}")

                with open(
                    f"lastfm_response_batch{batch_num}.xml",
                    'w',
                    encoding='utf-8'
                ) as f:
                    f.write(response.text)

            if ignored == 0:
                print(
                    f"✅ Batch {batch_num}/{total_batches} "
                    f"confirmed: {accepted}/{expected} accepted."
                )
            else:
                print(
                    f"⚠️ Batch {batch_num}/{total_batches}: "
                    f"{accepted} accepted, "
                    f"{ignored} ignored."
                )

            return failed_songs

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:

            print(f"\n⚠️ Network error during batch {batch_num}: {e}")
            print(
                "🔍 Checking Last.fm to see what actually landed "
                "before retrying..."
            )

            # Give Last.fm a moment to finish processing
            time.sleep(5)

            return self._verify_and_retry(
                songs_batch,
                timestamps_batch,
                batch_num
            )

        except Exception as e:

            print(f"\n❌ Error during batch {batch_num}: {e}")
            print("🔍 Verifying with Last.fm before retrying...")

            time.sleep(3)

            return self._verify_and_retry(
                songs_batch,
                timestamps_batch,
                batch_num
            )

    def _verify_and_retry(
        self,
        songs_batch,
        timestamps_batch,
        batch_num
    ):

        recent = self.get_recent_scrobbles(limit=200)

        if recent is None:
            # If we cant verify, ask the user
            print(
                "\n⚠️ Could not verify with Last.fm. "
                "Retrying may cause duplicate scrobbles."
            )
            answer = input(
                "Retry anyway? (yes/no): "
            ).strip().lower()

            if answer != 'yes':
                print("⏭️ Skipping this batch. Songs marked as failed.")
                return [
                    {
                        'artist': s['artist'],
                        'track': s['track'],
                        'album': s.get('album'),
                        'error': 'skipped after unverifiable failure'
                    }
                    for s in songs_batch
                ]

            return self.scrobble_individually(
                songs_batch, timestamps_batch
            )

        # Figure out which songs already landed
        already_scrobbled = []
        needs_retry = []
        needs_retry_timestamps = []

        for i, song in enumerate(songs_batch):
            key = (
                song['artist'].lower().strip(),
                song['track'].lower().strip(),
                timestamps_batch[i]
            )

            if key in recent:
                already_scrobbled.append(song)
            else:
                needs_retry.append(song)
                needs_retry_timestamps.append(timestamps_batch[i])

        print(
            f"\n📊 Verification result:"
        )
        print(
            f"   Already on Last.fm: {len(already_scrobbled)}"
        )
        print(
            f"   Need to retry: {len(needs_retry)}"
        )

        if not needs_retry:
            print(
                "✅ Entire batch already landed on Last.fm! "
                "No duplicates created."
            )
            return []

        print(f"🔄 Retrying {len(needs_retry)} missing songs...")

        return self.scrobble_individually(
            needs_retry, needs_retry_timestamps
        )

    def get_ignore_reason(self, code):
        """Explain Last.fm ignored-message codes."""

        reasons = {
            0: "No error",
            1: "Artist was filtered",
            2: "Track was filtered",
            3: "Timestamp was too far in the past",
            4: "Timestamp was too far in the future",
            5: "Maximum daily scrobble limit exceeded"
        }

        return reasons.get(
            code,
            f"Unknown Last.fm ignored code {code}"
        )

    def scrobble_individually(
        self,
        songs_batch,
        timestamps_batch
    ):
        """
        Fallback method.
        Each song is sent individually so we can identify
        exactly which song Last.fm rejects.
        """

        failed_songs = []
        success_count = 0

        for i, song in enumerate(songs_batch):

            try:

                # Use pylast for individual fallback
                self.network.scrobble(
                    artist=song['artist'],
                    title=song['track'],
                    timestamp=timestamps_batch[i],
                    album=song.get('album')
                )

                success_count += 1

                print(
                    f"  ✓ Scrobbled: "
                    f"{song['artist']} - {song['track']}"
                )

                time.sleep(0.5)

            except Exception as e:

                print(
                    f"  ✗ Failed: "
                    f"{song['artist']} - {song['track']}"
                )
                print(f"    Error: {e}")

                failed_songs.append({
                    'artist': song['artist'],
                    'track': song['track'],
                    'album': song.get('album'),
                    'error': str(e)
                })

        print(
            f"\n📊 Fallback complete: "
            f"{success_count} succeeded, "
            f"{len(failed_songs)} failed."
        )

        return failed_songs

    def process_file(self, file_number):
        """Process a single CSV file."""

        filepath = f"MusicCSV/part{file_number}.csv"

        if not os.path.exists(filepath):
            print(f"❌ File not found: {filepath}")
            return False

        print(f"\n{'=' * 50}")
        print(f"📂 Processing: {filepath}")
        print(
            f"📅 Date: "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print(f"{'=' * 50}\n")

        songs = self.read_csv_file(filepath)

        if not songs:
            print("❌ No valid songs to scrobble!")
            return False

        print("\n📋 Sample of songs to be scrobbled:")
        print("-" * 50)

        for i, song in enumerate(songs[:5]):
            album_str = (
                f" [{song['album']}]"
                if song.get('album')
                else ""
            )
            print(
                f"{i + 1}. "
                f"{song['artist']} - {song['track']}{album_str}"
            )

        if len(songs) > 5:
            print(f"... and {len(songs) - 5} more songs")

        print("-" * 50)

        confirm = input(
            "\nDo you want to proceed? (yes/no): "
        ).strip().lower()

        if confirm not in ('y', 'yes', 'yeah', 'yep'):
            print("❌ Cancelled by user")
            return False

        print("\n🚀 Starting scrobbling process...\n")

        # Timestamp calculation
        now = int(time.time())
        total_songs = len(songs)

        all_timestamps = [
            now - ((total_songs - i) * 30)
            for i in range(total_songs)
        ]

        batch_size = 50

        total_batches = (
            total_songs + batch_size - 1
        ) // batch_size

        failed_songs = []
        interrupted = False

        try:

            for batch_num in range(total_batches):

                start_idx = batch_num * batch_size

                end_idx = min(
                    start_idx + batch_size,
                    total_songs
                )

                batch = songs[start_idx:end_idx]
                batch_timestamps = all_timestamps[start_idx:end_idx]

                print(
                    f"\nProcessing songs "
                    f"{start_idx + 1} to {end_idx}..."
                )

                batch_failed = self.scrobble_batch(
                    batch,
                    batch_num + 1,
                    total_batches,
                    batch_timestamps
                )

                failed_songs.extend(batch_failed)

                if batch_num < total_batches - 1:
                    print(
                        "⏳ Waiting 3 seconds "
                        "before next batch..."
                    )
                    time.sleep(3)

        except KeyboardInterrupt:
            interrupted = True
            print(
                "\n\n⚠️ Interrupted by user (Ctrl+C)!"
            )
            print(
                "💾 Saving what we have so far..."
            )

        print(f"\n{'=' * 50}")
        print("📊 SUMMARY")
        print(f"{'=' * 50}")

        successful_count = total_songs - len(failed_songs)

        print(f"📦 Total songs: {total_songs}")
        print(f"✅ Accepted: {successful_count}")
        print(f"❌ Failed/ignored: {len(failed_songs)}")
        print(f"📊 Result: {successful_count}/{total_songs}")

        if failed_songs:
            failed_file = f"failed_songs_part{file_number}.json"

            with open(
                failed_file,
                'w',
                encoding='utf-8'
            ) as f:
                json.dump(
                    failed_songs,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            print(
                f"\n💾 {len(failed_songs)} "
                f"failed songs saved to:"
            )
            print(f"   {failed_file}")
        else:
            print("\n🎉 Last.fm reported zero ignored songs!")

        if failed_songs or interrupted:
            print(
                "\n⚠️ File NOT marked as completed "
                "(failures or interruption)."
            )
            return False

        self.save_progress(file_number)
        return True

    def save_progress(self, file_number):
        """Save progress."""

        progress_file = "scrobble_progress.json"

        try:

            if os.path.exists(progress_file):
                with open(
                    progress_file,
                    'r',
                    encoding='utf-8'
                ) as f:
                    progress = json.load(f)
            else:
                progress = {
                    'completed': [],
                    'last_run': {}
                }

            if file_number not in progress['completed']:
                progress['completed'].append(file_number)

            progress['last_run'] = {
                'file': f"part{file_number}.csv",
                'date': datetime.now().isoformat(),
                'timestamp': int(time.time())
            }

            with open(
                progress_file,
                'w',
                encoding='utf-8'
            ) as f:
                json.dump(progress, f, indent=2)

        except Exception as e:
            print(f"⚠️ Could not save progress: {e} bwaaa")

    def check_progress(self):
        """Check progress status."""

        progress_file = "scrobble_progress.json"

        available = self.list_part_indices()

        if os.path.exists(progress_file):
            try:
                with open(
                    progress_file,
                    'r',
                    encoding='utf-8'
                ) as f:
                    progress = json.load(f)
            except Exception:
                progress = {
                    'completed': [],
                    'last_run': {}
                }
        else:
            progress = {
                'completed': [],
                'last_run': {}
            }

        completed = sorted(
            set(progress.get('completed', []))
        )

        remaining = [
            i for i in available if i not in completed
        ]

        print("\n📊 PROGRESS STATUS:")
        print("=" * 50)
        print(
            f"Available files: "
            f"{[f'part{i}.csv' for i in available]}"
        )
        print(f"Completed files: {completed}")

        if remaining:
            print(
                "Remaining files: "
                + ", ".join(
                    f"part{i}.csv" for i in remaining
                )
            )
        else:
            print("All files completed!")

        print("=" * 50)
        print()

        return completed


def main():

    print("""
    ╔════════════════════════════════════════════╗
    ║   Last.fm Scrobbler v4.0 by BIG MIKE :3    ║
    ╚════════════════════════════════════════════╝
    """)

    try:
        scrobbler = LastFMScrobbler()

        available = scrobbler.list_part_indices()

        if not available:
            print(
                "❌ No part*.csv files found "
                "in MusicCSV/ o~O"
            )
            return

        completed = scrobbler.check_progress()

        remaining = [
            i for i in available if i not in completed
        ]

        if not remaining:
            print("✅ All files have been processed hehe :p")
            return

        next_file = remaining[0]

        print(
            f"📌 Next file to process: "
            f"part{next_file}.csv"
        )

        print("\nOptions:")
        print("1. Process next file automatically")
        print("2. Choose a specific file")
        print("3. Check a CSV file for issues")
        print("4. Exit")

        choice = input(
            "\nEnter your choice (1-4): "
        ).strip()

        if choice == '1':
            scrobbler.process_file(next_file)

        elif choice == '2':
            nums_list = ", ".join(str(i) for i in available)

            try:
                file_num = int(
                    input(
                        f"Enter file number ({nums_list}): "
                    )
                )
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
                    input(
                        "Enter file number to check "
                        f"({nums_list}): "
                    )
                )
            except ValueError:
                print("❌ Invalid number sillyy!")
                return

            if file_num in available:
                filepath = f"MusicCSV/part{file_num}.csv"
                songs = scrobbler.read_csv_file(filepath)

                if songs:
                    print(
                        f"\n✅ File is readable! "
                        f"Contains {len(songs)} valid songs"
                    )
                    print("\nFirst 10 songs:")

                    for i, song in enumerate(songs[:10], 1):
                        album_str = (
                            f" [{song['album']}]"
                            if song.get('album')
                            else ""
                        )
                        print(
                            f"{i}. "
                            f"{song['artist']} - "
                            f"{song['track']}{album_str}"
                        )
            else:
                print("❌ Invalid file number!")

        elif choice == '4':
            print("👋 cyaaaa > <")

        else:

            print("❌ Invalid choice sillyy! Please pick 1-4.")

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. cyaaaa > <")


if __name__ == "__main__":
    main()
