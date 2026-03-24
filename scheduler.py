"""
YouTube to Shorts — Auto Scheduler
====================================
Picks a random video from channels.txt, creates 1 Short, uploads as private.
Run by Windows Task Scheduler at 9 AM and 9 PM automatically.

FIRST TIME SETUP:
  1. Fill in channels.txt with YouTube channel URLs
  2. Run manually once to test: python scheduler.py
  3. Set up Task Scheduler (see guide)
"""

import os
import sys
import json
import random
import subprocess   
import logging
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# CONFIG — change these if needed
# ─────────────────────────────────────────────────────────────

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
CHANNELS_FILE = os.path.join(SCRIPT_DIR, "channels.txt")
HISTORY_FILE  = os.path.join(SCRIPT_DIR, "processed_videos.json")
LOG_FILE      = os.path.join(SCRIPT_DIR, "scheduler.log")
MAIN_SCRIPT   = os.path.join(SCRIPT_DIR, "yts_ollama.py")

SHORTS_PER_RUN  = 1
PRIVACY         = "private"
OLLAMA_MODEL    = "llama3.2:latest"
WHISPER_MODEL   = "base"
MAX_VIDEOS      = 20   # how many recent videos to fetch per channel

# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────

def load_channels():
    if not os.path.exists(CHANNELS_FILE):
        log.error(f"channels.txt not found: {CHANNELS_FILE}")
        log.error("Create it and add one YouTube channel URL per line.")
        sys.exit(1)

    channels = []
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                channels.append(line)

    if not channels:
        log.error("channels.txt is empty — add at least one channel URL!")
        sys.exit(1)

    log.info(f"Loaded {len(channels)} channel(s)")
    return channels


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed": []}


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def fetch_videos_from_channel(channel_url):
    """Use yt-dlp to list recent videos from a channel."""
    cookies_path = os.path.join(SCRIPT_DIR, "cookies.txt")
    cmd = [
        "yt-dlp",
        "--cookies", cookies_path,
        "--flat-playlist",
        "--playlist-end", str(MAX_VIDEOS),
        "--print", "%(id)s|%(duration)s|%(title)s",
        "--no-warnings",
        "--quiet",
        channel_url
    ]

    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="ignore")

    if result.returncode != 0 or not result.stdout:
        log.warning(f"Could not fetch from {channel_url}")
        return []

    videos = []
    for line in result.stdout.strip().splitlines():
        parts = line.strip().split("|")
        if not parts:
            continue
        video_id = parts[0].strip()
        try:
            duration = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else 0
        except:
            duration = 0
        title = parts[2].strip() if len(parts) > 2 else ""

# Accept videos 30 seconds to 3 hours, or unknown duration (NA)
        if (5000 <= duration <= 10800 or duration == 0) and video_id:
            videos.append({"id": video_id, "duration": duration, "title": title})

    log.info(f"  {channel_url} → {len(videos)} usable video(s)")
    return videos


def pick_video(channels, history):
    """Pick a random video that hasn't been processed yet."""
    processed = set(history["processed"])

    random.shuffle(channels)
    all_videos = []

    for ch in channels:
        vids = fetch_videos_from_channel(ch)
        fresh = [v for v in vids if v["id"] not in processed]
        all_videos.extend(fresh)

    if not all_videos:
        log.warning("All videos already processed — resetting history!")
        history["processed"] = []
        save_history(history)
        # Try again with empty history
        for ch in channels:
            all_videos.extend(fetch_videos_from_channel(ch))

    if not all_videos:
        log.error("No videos found from any channel. Check channels.txt")
        sys.exit(1)

    chosen = random.choice(all_videos)
    log.info(f"Picked: [{chosen['id']}] {chosen['title']}")
    return chosen


def run_pipeline(video_id):
    """Call the main shorts script."""
    log.info(f"Running pipeline for video: {video_id}")

    cmd = [
        sys.executable,
        MAIN_SCRIPT,
        "--video_id",      video_id,
        "--max_shorts",    str(SHORTS_PER_RUN),
        "--privacy",       PRIVACY,
        "--whisper_model", WHISPER_MODEL,
        "--ollama_model",  OLLAMA_MODEL,
    ]

    result = subprocess.run(cmd, cwd=SCRIPT_DIR)

    if result.returncode == 0:
        log.info(f"✅ Pipeline finished for {video_id}")
        return True
    else:
        log.error(f"❌ Pipeline failed for {video_id}")
        return False


# ── main ─────────────────────────────────────────────────────

def main():
    log.info("=" * 55)
    log.info("  🎬 YouTube to Shorts — Auto Scheduler")
    log.info(f"  🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 55)

    channels = load_channels()
    history  = load_history()

    log.info(f"Videos processed so far: {len(history['processed'])}")

    video = pick_video(channels, history)
    success = run_pipeline(video["id"])

    if success:
        history["processed"].append(video["id"])
        history[video["id"]] = {
            "title":        video.get("title", ""),
            "processed_at": datetime.now().isoformat(),
        }
        save_history(history)
        log.info(f"Saved to history: {video['id']}")
    else:
        log.warning("Not saving to history — will retry next run")

    log.info("=" * 55)
    log.info("  Run complete!")
    log.info("=" * 55)


if __name__ == "__main__":
    main()
