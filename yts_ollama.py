"""
YouTube to Shorts Automation Script (Ollama Edition)
=====================================================
Automatically converts long YouTube videos into multiple YouTube Shorts.
Uses local Ollama for AI — completely free, no API keys needed!

REQUIREMENTS (install once):
  pip install yt-dlp openai-whisper google-auth google-auth-oauthlib google-api-python-client requests
  Also: ffmpeg must be installed and in PATH (https://ffmpeg.org)
  Also: Ollama must be running (ollama serve)

USAGE:
  python youtube_to_shorts.py --video_id VIDEO_ID [options]

  Examples:
    python n8n_yts.py --video_id dQw4w9WgXcQ --max_shorts 2 --skip_upload
    python n8n_yts.py --video_id dQw4w9WgXcQ --max_shorts 3 --privacy private
    python n8n_yts.py --video_id dQw4w9WgXcQ --schedule_start "2025-06-01T08:00:00Z" --interval_hours 24
"""

import os
import sys
import json
import time
import argparse
import subprocess
import re
import requests
from datetime import datetime, timedelta, timezone

# ─────────────────────────────────────────────────────────────
# CONFIG — EDIT THESE IF NEEDED
# ─────────────────────────────────────────────────────────────

OLLAMA_HOST = "http://127.0.0.1:11434"   # Ollama API endpoint (default)
OLLAMA_MODEL = "llama3.2:latest"          # Model to use — change to "qwen3:4b" if preferred

YOUTUBE_CLIENT_SECRET_FILE = "client_secret.json"  # Download from Google Cloud Console (Desktop app)
YOUTUBE_TOKEN_FILE = "youtube_token.json"           # Auto-created on first run

WHISPER_MODEL = "base"       # "tiny" (fastest) | "base" | "small" | "medium" | "large" (most accurate)
OUTPUT_DIR = "shorts_output" # Folder to save downloaded videos and rendered shorts

# ─────────────────────────────────────────────────────────────


def check_dependencies():
    print("\n🔍 Checking dependencies...")

    # FFmpeg
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        if result.returncode != 0:
            raise FileNotFoundError
        print("✅ FFmpeg found")
    except FileNotFoundError:
        print("❌ FFmpeg not found. Install it and add to PATH.")
        sys.exit(1)

    # yt-dlp
    try:
        import yt_dlp
        print("✅ yt-dlp found")
    except ImportError:
        print("❌ yt-dlp not installed. Run: pip install yt-dlp")
        sys.exit(1)

    # whisper
    try:
        import whisper
        print("✅ whisper found")
    except ImportError:
        print("❌ whisper not installed. Run: pip install openai-whisper")
        sys.exit(1)

    # Ollama running check
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            if OLLAMA_MODEL in models:
                print(f"✅ Ollama running with model: {OLLAMA_MODEL}")
            else:
                print(f"❌ Model '{OLLAMA_MODEL}' not found in Ollama.")
                print(f"   Available models: {models}")
                print(f"   Run: ollama pull {OLLAMA_MODEL}")
                sys.exit(1)
        else:
            raise Exception("Ollama not responding")
    except Exception as e:
        print(f"❌ Ollama not running or not reachable at {OLLAMA_HOST}")
        print("   Run: ollama serve")
        sys.exit(1)

    # google-api-python-client
    try:
        import googleapiclient
        print("✅ google-api-python-client found")
    except ImportError:
        print("❌ google-api-python-client not installed.")
        print("   Run: pip install google-auth google-auth-oauthlib google-api-python-client")
        sys.exit(1)

def download_video(video_id, output_dir):
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"
    final_path = os.path.join(output_dir, f"{video_id}.mp4")

    # Skip download if already exists
    if os.path.exists(final_path):
        print(f"\n📦 Video already downloaded: {final_path}")
        with yt_dlp.YoutubeDL({"quiet": True, "cookiefile": "cookies.txt"}) as ydl:
            info = ydl.extract_info(url, download=False)
            return final_path, info.get("title", ""), info.get("duration", 0)

    print(f"\n📥 Downloading video: {url}")

    # Call yt-dlp directly as command — more reliable than Python API
    cmd = [
        "yt-dlp",
        "--cookies", "cookies.txt",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
        "--merge-output-format", "mp4",
        "-o", final_path,
        url
    ]
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0 or not os.path.exists(final_path):
        print("❌ Download failed!")
        sys.exit(1)

    # Get title and duration
    with yt_dlp.YoutubeDL({"quiet": True, "cookiefile": "cookies.txt"}) as ydl:
        info = ydl.extract_info(url, download=False)

    print(f"✅ Downloaded: {final_path}")
    return final_path, info.get("title", ""), info.get("duration", 0)

def transcribe_video(video_path, model_name="base"):
    import whisper

    # Cache transcript
    transcript_cache = video_path.replace(".mp4", "_transcript.json")
    if os.path.exists(transcript_cache):
        print(f"\n📦 Using cached transcript")
        with open(transcript_cache) as f:
            data = json.load(f)
        return data["segments"], data["text"]

    print(f"\n🎙️  Transcribing with Whisper ({model_name} model)...")
    print("    This may take a few minutes for long videos...")

    model = whisper.load_model(model_name)
    result = model.transcribe(video_path, verbose=False)

    segments = [
        {"start": seg["start"], "end": seg["end"], "text": seg["text"].strip()}
        for seg in result["segments"]
    ]
    full_text = result.get("text", "")

    # Save cache
    with open(transcript_cache, "w") as f:
        json.dump({"segments": segments, "text": full_text}, f)

    print(f"✅ Transcribed {len(segments)} segments")
    return segments, full_text


def call_ollama(prompt, expect_json=True):
    """Call local Ollama API. Returns response text."""
    print(f"   🦙 Calling Ollama ({OLLAMA_MODEL})...", end="", flush=True)

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,      # Lower = more consistent/predictable output
            "num_predict": 2048,     # Max tokens to generate
        }
    }

    if expect_json:
        payload["format"] = "json"   # Forces Ollama to return valid JSON

    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=120  # 2 min timeout for slower machines
        )
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()
        print(" done!")
        return text
    except requests.exceptions.Timeout:
        print("\n❌ Ollama timed out. Try a smaller model like 'llama3.2:latest'")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ollama error: {e}")
        sys.exit(1)


def ask_ollama_for_clips(transcript_segments, full_text, video_title, max_shorts):
    print(f"\n🤖 Asking Ollama to find the best {max_shorts} clip moments...")

    transcript_text = ""
    for seg in transcript_segments:
        transcript_text += f"[{seg['start']:.1f}s - {seg['end']:.1f}s]: {seg['text']}\n"

    prompt = (
        f"You are a YouTube Shorts editor. Analyze this video transcript and find the {max_shorts} "
        f"best moments to turn into YouTube Shorts (30-59 seconds each).\n\n"
        f"Video Title: {video_title}\n\n"
        f"TRANSCRIPT:\n{transcript_text[:6000]}\n\n"
        f"Rules:\n"
        f"- Each clip must be 30-59 seconds long (end - start must be 30 to 59)\n"
        f"- Pick self-contained, interesting, funny, or surprising moments\n"
        f"- Do not pick overlapping time ranges\n"
        f"- Return ONLY a JSON array, nothing else\n\n"
        f"Return this exact JSON format:\n"
        f'[{{"start": 10.0, "end": 50.0, "hook": "short hook text", "reason": "why this clip"}}]\n'
    )

    raw = call_ollama(prompt, expect_json=True)

    # Extract JSON array from response
    # Try to find array in response
    json_match = re.search(r'\[.*?\]', raw, re.DOTALL)
    if json_match:
        raw = json_match.group(0)

    raw = re.sub(r"```json|```", "", raw).strip()

    try:
        clips = json.loads(raw)
        if not isinstance(clips, list):
            # Sometimes Ollama wraps in an object
            for key in clips:
                if isinstance(clips[key], list):
                    clips = clips[key]
                    break

        valid_clips = []
        for clip in clips:
            # Ensure required keys exist
            if "start" not in clip or "end" not in clip:
                continue
            clip["start"] = float(clip["start"])
            clip["end"] = float(clip["end"])
            duration = clip["end"] - clip["start"]
            if duration < 15:
                continue
            if duration > 60:
                clip["end"] = clip["start"] + 55
            valid_clips.append(clip)

        if not valid_clips:
            print("⚠️  Ollama returned no valid clips. Using fallback (every 50s).")
            return fallback_clips(full_text, max_shorts)

        print(f"✅ Ollama identified {len(valid_clips)} clips")
        for i, c in enumerate(valid_clips):
            print(f"   Clip {i+1}: {c['start']:.1f}s → {c['end']:.1f}s | {c.get('hook', '')}")
        return valid_clips

    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️  Could not parse Ollama response ({e}). Using fallback.")
        return fallback_clips(full_text, max_shorts)


def fallback_clips(full_text, max_shorts):
    """Simple fallback: pick clips every 60 seconds starting at 30s."""
    print("   Using fallback clip selection (every 60s)...")
    clips = []
    for i in range(max_shorts):
        start = 30 + (i * 65)
        clips.append({
            "start": float(start),
            "end": float(start + 55),
            "hook": f"Clip {i+1}",
            "reason": "Auto-selected"
        })
    return clips


def generate_metadata_ollama(clip, video_title, clip_index):
    print(f"\n📝 Generating metadata with Ollama...")

    prompt = (
        f"Generate YouTube Shorts metadata.\n"
        f"Video: {video_title}\n"
        f"Clip: {clip.get('hook', 'Interesting moment')}\n\n"
        f"Return ONLY this JSON:\n"
        f'{{"title": "catchy title under 100 chars with emoji", '
        f'"description": "2 sentences with hashtags #Shorts #YouTube", '
        f'"tags": ["tag1", "tag2", "tag3"]}}\n'
    )

    raw = call_ollama(prompt, expect_json=True)
    raw = re.sub(r"```json|```", "", raw).strip()

    try:
        metadata = json.loads(raw)
        # Ensure required keys
        if "title" not in metadata:
            metadata["title"] = f"{video_title[:70]} #Shorts"
        if "description" not in metadata:
            metadata["description"] = f"{video_title}\n\n#Shorts #YouTube"
        if "tags" not in metadata:
            metadata["tags"] = ["Shorts", "YouTube"]
        print(f"   Title: {metadata['title']}")
        return metadata
    except json.JSONDecodeError:
        print("   ⚠️  Using fallback metadata")
        return {
            "title": f"{video_title[:70]} #Shorts",
            "description": f"{video_title}\n\n#Shorts #YouTube",
            "tags": ["Shorts", "YouTube", "viral"]
        }


def cut_and_crop_clip(input_video, clip, output_path):
    start = clip["start"]
    duration = clip["end"] - clip["start"]

    print(f"\n✂️  Cutting: {start:.1f}s → {clip['end']:.1f}s ({duration:.1f}s)")

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", input_video,
        "-t", str(duration),
        "-vf", (
            "split[original][copy];"
            "[copy]scale=1080:1920,setsar=1,gblur=sigma=20[blurred];"
            "[original]scale=1080:-2[scaled];"
            "[blurred][scaled]overlay=(W-w)/2:(H-h)/2"
        ),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path
    ]

    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ FFmpeg error:\n{result.stderr[-1000:]}")
        return False

    file_size = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ Saved: {output_path} ({file_size:.1f} MB)")
    return True


def get_youtube_service():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None

    if os.path.exists(YOUTUBE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(YOUTUBE_TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(YOUTUBE_CLIENT_SECRET_FILE):
                print(f"❌ client_secret.json not found in current folder")
                print("   Download from Google Cloud Console → Credentials → Desktop app")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(YOUTUBE_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def upload_short(youtube, video_path, metadata, publish_at=None, privacy="private"):
    from googleapiclient.http import MediaFileUpload

    print(f"\n📤 Uploading: {metadata['title']}")

    status_body = {"privacyStatus": privacy}
    if publish_at:
        status_body["publishAt"] = publish_at
        status_body["privacyStatus"] = "private"

    body = {
        "snippet": {
            "title": metadata["title"][:100],
            "description": metadata["description"][:5000],
            "tags": metadata.get("tags", []),
            "categoryId": "22",
        },
        "status": status_body,
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=5*1024*1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"   Upload: {int(status.progress() * 100)}%", end="\r")

    video_id = response["id"]
    print(f"\n✅ Uploaded! https://youtube.com/shorts/{video_id}")
    if publish_at:
        print(f"   Scheduled: {publish_at}")
    return video_id


def calculate_schedule(start_time_str, interval_hours, count):
    if not start_time_str:
        return [None] * count
    start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
    return [
        (start_time + timedelta(hours=interval_hours * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for i in range(count)
    ]


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    global OLLAMA_MODEL
    parser = argparse.ArgumentParser(description="Convert YouTube video to Shorts (Ollama Edition)")
    parser.add_argument("--video_id", required=True, help="YouTube video ID (e.g. dQw4w9WgXcQ)")
    parser.add_argument("--max_shorts", type=int, default=3, help="Max Shorts to create (default: 3)")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    parser.add_argument("--schedule_start", default=None,
                        help="ISO 8601 publish start (e.g. 2025-06-01T08:00:00Z)")
    parser.add_argument("--interval_hours", type=int, default=24)
    parser.add_argument("--skip_upload", action="store_true",
                        help="Skip YouTube upload — just download, transcribe, and cut clips")
    parser.add_argument("--whisper_model", default=WHISPER_MODEL,
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--ollama_model", default=OLLAMA_MODEL,
                        help=f"Ollama model to use (default: {OLLAMA_MODEL})")
    args = parser.parse_args()

    # Allow overriding model via CLI

    OLLAMA_MODEL = args.ollama_model

    print("=" * 60)
    print("  🎬 YouTube to Shorts Automation (Ollama Edition)")
    print(f"  🦙 AI Model: {OLLAMA_MODEL} (local, free!)")
    print("=" * 60)

    check_dependencies()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    video_dir = os.path.join(OUTPUT_DIR, args.video_id)
    os.makedirs(video_dir, exist_ok=True)

    # Download (skips if already downloaded)
    video_path, video_title, video_duration = download_video(args.video_id, video_dir)
    print(f"   Title: {video_title}")
    print(f"   Duration: {video_duration // 60}m {video_duration % 60}s")

    if video_duration < 60:
        print("⚠️  Video is under 60s — already short enough!")
        sys.exit(0)

    # Transcribe (uses cache if already done)
    segments, full_text = transcribe_video(video_path, args.whisper_model)
    if not segments:
        print("❌ No transcript generated.")
        sys.exit(1)

    # AI clip selection via Ollama
    clips = ask_ollama_for_clips(segments, full_text, video_title, args.max_shorts)
    clips = clips[:args.max_shorts]

    # Schedule
    publish_times = calculate_schedule(args.schedule_start, args.interval_hours, len(clips))

    # YouTube auth
    youtube = None
    if not args.skip_upload:
        print("\n🔐 Authenticating with YouTube...")
        youtube = get_youtube_service()
        print("✅ YouTube authenticated")

    results = []

    for i, clip in enumerate(clips):
        print(f"\n{'─'*60}")
        print(f"  Processing Short {i+1}/{len(clips)}")
        print(f"{'─'*60}")

        clip_file = os.path.join(video_dir, f"short_{i+1:02d}.mp4")
        if not cut_and_crop_clip(video_path, clip, clip_file):
            print(f"⚠️  Skipping Short {i+1} due to FFmpeg error")
            continue

        metadata = generate_metadata_ollama(clip, video_title, i)

        if not args.skip_upload:
            vid_id = upload_short(youtube, clip_file, metadata, publish_times[i], args.privacy)
            results.append({
                "short": i + 1,
                "youtube_id": vid_id,
                "url": f"https://youtube.com/shorts/{vid_id}",
                "title": metadata["title"],
                "publish_at": publish_times[i] or "Immediate",
                "file": clip_file
            })
            if i < len(clips) - 1:
                time.sleep(3)
        else:
            results.append({"short": i + 1, "title": metadata["title"], "file": clip_file})

    print(f"\n{'='*60}")
    print("  ✅ DONE!")
    print(f"{'='*60}")
    for r in results:
        print(f"  Short {r['short']}: {r['title']}")
        if "url" in r:
            print(f"    → {r['url']}  (publishes: {r['publish_at']})")
        print(f"    File: {r['file']}")

    results_file = os.path.join(video_dir, "results.json")
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n📄 Full results: {results_file}")


if __name__ == "__main__":
    main()