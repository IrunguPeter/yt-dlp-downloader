import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

try:
    import yt_dlp
except ImportError:
    sys.exit(
        "yt-dlp is not installed. Install it with:\n"
        "    pip install yt-dlp"
    )


def ensure_ffmpeg():
    """Make sure ffmpeg is available (needed for merging video+audio)."""
    if shutil.which("ffmpeg") is None:
        print(
            "[!] ffmpeg not found on PATH. Some downloads may fail to merge "
            "audio/video. Install it from https://ffmpeg.org and add it to PATH."
        )
        return False
    return True


def build_cookies_opts(args):
    """Build yt-dlp cookie-related options from CLI args (Instagram auth)."""
    opts = {}
    if args.cookies_from_browser:
        opts["cookiesfrombrowser"] = (args.cookies_from_browser, None, None, None)
    if args.cookies:
        opts["cookiefile"] = args.cookies
    return opts


def build_base_opts(dest, args=None):
    opts = {
        "outtmpl": os.path.join(dest, "%(uploader)s - %(title)s [%(id)s].%(ext)s"),
        "noplaylist": False,
        "quiet": False,
        "no_warnings": False,
        "restrictfilenames": False,
        "ignoreerrors": True,
        "continuedl": True,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
        "writethumbnail": False,
        "progress_hooks": [progress_hook],
    }
    if args is not None:
        opts.update(build_cookies_opts(args))
    return opts


_IG_PATCHED = False


def patch_instagram_images():
    """The yt-dlp Instagram extractor emits no ``formats`` for image-only
    carousel items, so downloads fail with 'No video formats found!'. This
    monkeypatch turns those items into downloadable image entries using their
    highest-resolution thumbnail URL."""
    global _IG_PATCHED
    if _IG_PATCHED:
        return
    from yt_dlp.extractor.instagram import InstagramIE

    _orig_real_extract = InstagramIE._real_extract

    def _patched_real_extract(self, url):
        info = _orig_real_extract(self, url)
        if info.get("_type") == "playlist":
            new_entries = []
            for e in info.get("entries", []):
                formats = e.get("formats") or []
                if not formats and e.get("thumbnails"):
                    best = max(e["thumbnails"], key=lambda t: t.get("width") or 0)
                    ne = dict(e)
                    ne["formats"] = [{
                        "url": best["url"],
                        "ext": "jpg",
                        "format_id": "image",
                        "vcodec": None,
                        "acodec": "none",
                        "protocol": "https",
                    }]
                    ne["vcodec"] = "none"
                    new_entries.append(ne)
                else:
                    new_entries.append(e)
            info["entries"] = new_entries
        return info

    InstagramIE._real_extract = _patched_real_extract
    _IG_PATCHED = True


def progress_hook(d):
    if d["status"] == "downloading":
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        got = d.get("downloaded_bytes", 0)
        pct = (got / total * 100) if total else 0
        speed = d.get("speed")
        speed_txt = f"{speed / 1024 / 1024:.1f} MB/s" if speed else "?"
        eta = d.get("eta")
        eta_txt = f"{eta}s" if eta is not None else "?"
        print(f"\r  {pct:5.1f}%  {got/1024/1024:6.1f}/{total/1024/1024:6.1f} MB  [{speed_txt}]  ETA {eta_txt}", end="")
    elif d["status"] == "finished":
        print()


def download_instagram(url, dest, args):
    """Download Instagram posts/reels/stories. Instagram heavily rate-limits IPs."""
    patch_instagram_images()
    opts = build_base_opts(dest, args)
    opts.update(
        {
            "format": "bestvideo*+bestaudio/best",
            "merge_output_format": "mp4",
            "extract_flat": False,
        }
    )

    # Good practice for Instagram: avoid too many threads, modest retries.
    if ensure_ffmpeg() is False:
        opts["format"] = "best"

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        urls = info.get("_entries", [info]) if isinstance(info, dict) else [info]
        real = [u for u in urls if u]
        print(f"[i] Found {len(real)} item(s)")
        # Download sequentially with a small delay to reduce rate-limit risk.
        with yt_dlp.YoutubeDL(opts) as ydl2:
            try:
                ydl2.download([url])
            except Exception as e:
                print(f"[!] Failed to download {url}: {e}")


def download_generic(url, dest, args):
    opts = build_base_opts(dest, args)
    opts.update(
        {
            "format": "bestvideo*+bestaudio/best",
            "merge_output_format": "mp4",
        }
    )
    if not ensure_ffmpeg():
        opts["format"] = "best"
    if args.audio:
        opts.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": args.audio,
                        "preferredquality": args.audio_quality,
                    }
                ],
                "outtmpl": os.path.join(dest, "%(title)s [%(id)s].%(ext)s"),
            }
        )
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])


def main():
    parser = argparse.ArgumentParser(
        description="Download images and videos (esp. Instagram) using yt-dlp."
    )
    parser.add_argument("url", nargs="*", help="URL(s) to download")
    parser.add_argument("--file", "-f", help="Read URLs from a text file, one per line")
    parser.add_argument("--dest", "-d", default="downloads", help="Output directory")
    parser.add_argument(
        "--instagram", action="store_true",
        help="Treat URLs as Instagram (carousel/reel/story aware, rate-limit friendly)",
    )
    parser.add_argument(
        "--cookies", "-c", metavar="FILE",
        help="Path to a Netscape-format cookies.txt file for authentication (e.g. for "
             "Instagram posts that require login)",
    )
    parser.add_argument(
        "--cookies-from-browser", metavar="BROWSER",
        help="Use cookies from an installed browser: chrome, chromium, edge, firefox, "
             "opera, safari ... (e.g. --cookies-from-browser chrome)",
    )
    parser.add_argument(
        "--audio", choices=["mp3", "m4a", "opus", "wav", "flac"],
        help="Extract audio only to this format instead of downloading video",
    )
    parser.add_argument("--audio-quality", default="0",
                        help="Audio quality (0 is best, default already 0)")
    parser.add_argument(
        "--update", action="store_true",
        help="Update yt-dlp to the latest version and exit",
    )
    args = parser.parse_args()

    if args.update:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"])
        return

    urls = list(args.url)
    if args.file:
        if not os.path.isfile(args.file):
            sys.exit(f"URL file not found: {args.file}")
        with open(args.file, encoding="utf-8") as fh:
            urls += [
                line.strip()
                for line in fh
                if line.strip() and not line.strip().startswith(("#", "//"))
            ]

    if not urls:
        parser.print_help()
        sys.exit("\nPlease provide at least one URL or --file.")

    os.makedirs(args.dest, exist_ok=True)
    print(f"[i] Saving to: {os.path.abspath(args.dest)}")

    for url in urls:
        print(f"\n=== {url} ===")
        if args.instagram or "instagram.com" in url:
            download_instagram(url, args.dest, args)
        else:
            download_generic(url, args.dest, args)


if __name__ == "__main__":
    main()
