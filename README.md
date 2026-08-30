# Media Downloader

A Python tool to download images and videos using [yt-dlp](https://github.com/yt-dlp/yt-dlp), with special handling for Instagram reels, posts, and carousels (rate-limit friendly, image-carousel aware).

Works on **Windows**, **Linux**, and in **Docker**.

## Requirements

- [Python 3.8+](https://www.python.org/downloads/)
- [ffmpeg](https://ffmpeg.org) on your PATH (recommended — needed to merge
  video + audio into a single file). Optional but most video downloads need it.
- Or **Docker** (no Python/ffmpeg needed).

---

## Windows

### Installation

```powershell
pip install yt-dlp
```

### Usage

```
python download_media.py [URL...] [options]
```

Download an Instagram reel/post:

```powershell
python download_media.py "https://www.instagram.com/reel/xxxx/"
```

Download a whole carousel / mixed post (images + videos):

```powershell
python download_media.py "https://www.instagram.com/p/DEQbo-WIJIww/"
```

Download multiple URLs (Instagram is auto-detected):

```powershell
python download_media.py "https://www.instagram.com/p/xxx/" "https://www.youtube.com/watch?v=yyy"
```

Download a batch of URLs from a file (one per line, `#` for comments):

```powershell
python download_media.py --file urls.txt --dest ./my_media
```

Extract audio only (e.g. MP3):

```powershell
python download_media.py --audio mp3 URL
```

Update yt-dlp to the latest version:

```powershell
python download_media.py --update
```

---

## Linux

### Installation (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install -y python3 python3-pip ffmpeg
pip install --user yt-dlp
```

On other distros, install `python3`, `pip`, and `ffmpeg` via your package
manager (e.g. `sudo pacman -S python python-pip ffmpeg` on Arch, or
`sudo dnf install python3 python3-pip ffmpeg` on Fedora).

Make sure the script is executable and on your PATH if desired:

```bash
chmod +x download_media.py
```

### Usage

```bash
python3 download_media.py "https://www.instagram.com/p/xxxxx/"
python3 download_media.py --cookies cookies.txt "https://www.instagram.com/p/xxxxx/"
python3 download_media.py --audio mp3 URL
python3 download_media.py --update
```

If `python3` isn't found after a `--user` install, add it to your PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

---

## Docker

### One-off run (recommended)

Download a URL into a local `./downloads` folder with the current user's
permissions:

```bash
docker run --rm \
  -v "$(pwd)/downloads:/app/downloads" \
  -v "$(pwd)/cookies.txt:/cookies.txt:ro" \
  ghcr.io/irungupeter/yt-dlp-downloader:latest \
  --cookies /cookies.txt "https://www.instagram.com/p/xxxxx/"
```

Download without cookies:

```bash
docker run --rm -v "$(pwd)/downloads:/app/downloads" \
  ghcr.io/irungupeter/yt-dlp-downloader:latest "https://www.youtube.com/watch?v=..."
```

> `-v "$(pwd)/downloads:/app/downloads"` maps the container's default download
> folder to a folder on your machine, so files persist after the container exits.
> Mount `cookies.txt` read-only if you need Instagram auth.

### Portability / uid note

The container defaults to running as **root** so downloaded files are owned by
root. To write files owned by your user, run with `--user "$(id -u):$(id -g)"`:

```bash
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$(pwd)/downloads:/app/downloads" \
  ghcr.io/irungupeter/yt-dlp-downloader:latest "URL"
```

### docker compose

Create a `docker-compose.yml` (see the repo) and run:

```bash
docker compose run --rm ydl "https://www.instagram.com/p/xxxxx/"
```

### Build the image yourself (optional)

```bash
docker build -t yt-dlp-downloader .
docker run --rm -v "$(pwd)/downloads:/app/downloads" yt-dlp-downloader "URL"
```

### Deploy on a home server

The image is published automatically to GitHub Container Registry whenever
changes are pushed to `main` (via the GitHub Actions workflow):

```text
ghcr.io/irungupeter/yt-dlp-downloader:latest
```

On your server (Docker installed), one-off download:

```bash
docker run --rm \
  -v "$HOME/yt-downloads:/app/downloads" \
  -v "$HOME/cookies.txt:/cookies.txt:ro" \
  ghcr.io/irungupeter/yt-dlp-downloader:latest \
  --cookies /cookies.txt "https://www.instagram.com/p/xxxxx/"
```

Run files as your user instead of root:

```bash
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$HOME/yt-downloads:/app/downloads" \
  ghcr.io/irungupeter/yt-dlp-downloader:latest "URL"
```

Pull the latest image on the server after updates:

```bash
docker pull ghcr.io/irungupeter/yt-dlp-downloader:latest
```

> First pull may require a one-time login to GHCR if the repo is private. This
> repo is **public**, so no login is needed.

---

## Common options

| Option | Description |
|--------|-------------|
| `-f, --file <file>` | Read URLs from a text file, one per line |
| `-d, --dest <dir>` | Output directory (default: `downloads`) |
| `--instagram` | Treat URLs as Instagram (carousel/reel aware, rate-limit friendly) |
| `--audio <fmt>` | Extract audio only to: `mp3`, `m4a`, `opus`, `wav`, `flac` |
| `--audio-quality <n>` | Audio quality, 0 is best (default `0`) |
| `--update` | Update yt-dlp and exit |
| `-c, --cookies <file>` | Use a Netscape-format `cookies.txt` for authentication |
| `--cookies-from-browser <browser>` | Use login cookies from a browser: `chrome`, `chromium`, `edge`, `firefox`, `opera`, `safari` |

---

## Instagram authentication (important)

Most Instagram posts are **follow-only / login-gated**, so they fail with
"This content is only available for registered users who follow this account"
unless you pass login cookies.

**Recommended:** export a `cookies.txt` and pass it with `--cookies`:

```bash
python3 download_media.py --cookies cookies.txt "https://www.instagram.com/p/xxxxx/"
```

How to get `cookies.txt`:
1. In Chrome, log into [instagram.com](https://www.instagram.com) with an
   account that **follows** the posting account.
2. Install the **"Get cookies.txt LOCALLY"** extension.
3. While on instagram.com, click the extension → **Export**, save as `cookies.txt`.

> Note: cookies expire (roughly weekly, or after logout). When downloads start
> failing again with the "only available for registered users" error, just
> re-export the file and overwrite it.

Alternatively, you can pull cookies directly from a browser

```bash
python3 download_media.py --cookies-from-browser edge "URL"
```

> On Windows, `--cookies-from-browser` often fails with
> "Failed to decrypt with DPAPI" on newer Chrome/Edge (app-bound encryption)
> and with "Permission denied" while the browser is running (close it first).
> The `cookies.txt` export is the reliable path.

## Instagram image carousels

Image-only carousel items previously errored with "No video formats found!",
because yt-dlp's Instagram extractor emits no video formats for images. The
script applies an automatic patch that downloads these as full-resolution
images, so posts/reels/carousels — mixed image and video — download correctly.

## Notes on Instagram

- Instagram heavily rate-limits by IP. Frequent or large downloads may hit
  **429 "Too Many Requests"** errors.
- Many Instagram posts are **follow-only** and require you to be logged in. Use
  the `--cookies cookies.txt` method described above.
- Image carousels are handled automatically (see the section above).

## License

MIT
