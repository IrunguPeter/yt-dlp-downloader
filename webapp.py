import os
import sys
import threading
import queue
import io

from flask import (
    Flask,
    request,
    jsonify,
    render_template_string,
    send_from_directory,
    Response,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DEST = os.path.join(BASE_DIR, "downloads")
COOKIES_DIR = os.path.join(BASE_DIR, "cookies")

app = Flask(__name__)

# Global job state: job_id -> dict
JOBS = {}
JOB_COUNTER = 0
JOB_LOCK = threading.Lock()

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Media Downloader</title>
<style>
  :root{
    --bg:#0f1115; --panel:#171a21; --panel2:#1e222b; --border:#2a2f3a;
    --text:#e6e8ee; --muted:#9aa3b2; --accent:#4f8cff; --accent2:#3b6fd6;
    --ok:#37c978; --warn:#f0b124; --err:#ef5350;
  }
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,
    Helvetica,Arial,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
  .wrap{max-width:960px;margin:0 auto;padding:32px 20px 80px}
  h1{font-size:24px;margin:0 0 4px}
  .sub{color:var(--muted);font-size:14px;margin:0 0 24px}
  .panel{background:var(--panel);border:1px solid var(--border);border-radius:14px;
    padding:20px;margin-bottom:20px}
  .panel h2{font-size:15px;margin:0 0 14px;color:var(--muted);font-weight:600;
    text-transform:uppercase;letter-spacing:.4px}
  label{display:block;font-size:13px;color:var(--muted);margin:0 0 6px}
  textarea,input[type=text]{
    width:100%;background:var(--panel2);border:1px solid var(--border);
    border-radius:10px;color:var(--text);padding:12px;font-size:14px;
    resize:vertical;font-family:inherit}
  textarea:focus,input:focus{outline:none;border-color:var(--accent)}
  .row{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end}
  .row > .grow{flex:1;min-width:220px}
  .check{display:flex;align-items:center;gap:8px;font-size:14px;color:var(--text);
    margin-top:16px;cursor:pointer}
  .check input{width:16px;height:16px;accent-color:var(--accent)}
  .btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;
    background:var(--accent);color:#fff;border:none;border-radius:10px;
    padding:12px 20px;font-size:15px;font-weight:600;cursor:pointer;
    transition:background .15s}
  .btn:hover{background:var(--accent2)}
  .btn:disabled{opacity:.5;cursor:not-allowed}
  .btn.ghost{background:var(--panel2);border:1px solid var(--border);color:var(--text)}
  .btn.small{padding:6px 12px;font-size:13px;border-radius:8px}
  .hint{font-size:12px;color:var(--muted);margin:12px 0 0}
  #jobs{list-style:none;padding:0;margin:0}
  #jobs li{background:var(--panel2);border:1px solid var(--border);border-radius:10px;
    padding:14px;margin-bottom:10px}
  .job-top{display:flex;justify-content:space-between;gap:10px;align-items:center;
    margin-bottom:8px}
  .job-url{font-size:13px;word-break:break-all;color:var(--muted)}
  .status{font-size:12px;font-weight:700;padding:3px 8px;border-radius:20px;
    white-space:nowrap}
  .status.run{background:rgba(79,140,255,.15);color:var(--accent)}
  .status.done{background:rgba(55,201,120,.15);color:var(--ok)}
  .status.err{background:rgba(239,83,80,.15);color:var(--err)}
  .status.pending{background:rgba(154,163,178,.15);color:var(--muted)}
  .log{background:#0b0d12;border:1px solid var(--border);border-radius:8px;
    padding:10px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
    font-size:12px;color:#a8c0e0;white-space:pre-wrap;word-break:break-word;
    max-height:220px;overflow-y:auto}
  table{width:100%;border-collapse:collapse;font-size:14px}
  td{padding:8px 4px;border-bottom:1px solid var(--border)}
  td a{color:var(--accent);text-decoration:none;word-break:break-all}
  td a:hover{text-decoration:underline}
  .empty{color:var(--muted);font-size:14px}
  .toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);
    background:var(--panel2);border:1px solid var(--border);border-radius:10px;
    padding:12px 18px;font-size:14px;display:none;z-index:50;box-shadow:0 8px 30px rgba(0,0,0,.4)}
</style>
</head>
<body>
<div class="wrap">
  <h1>🎬 Media Downloader</h1>
  <p class="sub">Downloads videos &amp; images via <b>yt-dlp</b> — YouTube, Instagram,
    and hundreds of other sites.</p>

  <div class="panel">
    <h2>New Download</h2>
    <form id="dlForm" enctype="multipart/form-data">
      <label for="urls">URL(s) — one per line</label>
      <textarea id="urls" name="urls" rows="4" placeholder="https://www.youtube.com/watch?v=..."></textarea>

      <div class="row" style="margin-top:14px">
        <div class="grow">
          <label>Or upload a URL list (.txt)</label>
          <input type="file" id="file" name="file" accept=".txt,text/plain">
        </div>
        <div class="grow">
          <label>Cookies file for Instagram login</label>
          <input type="file" id="cookies" name="cookies" accept=".txt">
        </div>
      </div>

      <div class="row" style="margin-top:14px">
        <div class="grow">
          <label>Destination folder</label>
          <input type="text" id="dest" name="dest" value="{{ default_dest }}" placeholder="downloads">
        </div>
      </div>

      <label class="check">
        <input type="checkbox" id="audio" name="audio">
        Extract audio only (MP3)
      </label>

      <button type="submit" class="btn" id="submitBtn">⬇ &nbsp;Download</button>
      <p class="hint">Each URL is queued and processed one at a time. Instagram posts
        generally require a cookies file to bypass the login wall.</p>
    </form>
  </div>

  <div class="panel">
    <h2>Downloaded Files</h2>
    <div id="filesBox"><p class="empty">Loading…</p></div>
  </div>

  <div class="panel">
    <h2>Jobs</h2>
    <ul id="jobs"><li class="empty" style="list-style:none">No jobs yet.</li></ul>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const MAX_LOG = 4000;

function toast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(()=>{ t.style.display='none'; }, 4000);
}

async function loadFiles(){
  try{
    const r = await fetch('/api/files');
    const data = await r.json();
    const box = document.getElementById('filesBox');
    if(!data.files.length){ box.innerHTML = '<p class="empty">No files downloaded yet.</p>'; return; }
    let html = '<table>';
    for(const f of data.files){
      const size = (f.size/1048576).toFixed(1);
      html += `<tr><td><a href="/files/${encodeURIComponent(f.name)}">${f.name}</a></td>
        <td style="text-align:right;color:var(--muted);white-space:nowrap">${size} MB</td></tr>`;
    }
    html += '</table>';
    box.innerHTML = html;
  }catch(e){ box.innerHTML = '<p class="empty">Could not load files.</p>'; }
}

async function refreshJobs(){
  try{
    const r = await fetch('/api/jobs');
    const jobs = await r.json();
    const ul = document.getElementById('jobs');
    if(!jobs.length){ ul.innerHTML = '<li class="empty" style="list-style:none">No jobs yet.</li>'; return; }
    let html = '';
    for(const j of jobs){
      const url = j.url.replace(/</g,'&lt;');
      const cls = j.status==='running'?'run':j.status==='done'?'done':j.status==='error'?'err':'pending';
      const log = j.log.length>MAX_LOG ? '…'+j.log.slice(-MAX_LOG) : j.log;
      const safeLog = log.replace(/</g,'&lt;');
      html += `<li>
        <div class="job-top"><span class="job-url">${url}</span>
          <span class="status ${cls}">${j.status}</span></div>
        <pre class="log">${safeLog}</pre>
      </li>`;
    }
    ul.innerHTML = html;
  }catch(e){}
}

document.getElementById('dlForm').addEventListener('submit', async (ev)=>{
  ev.preventDefault();
  const fd = new FormData();
  fd.append('urls', document.getElementById('urls').value);
  const uf = document.getElementById('file').files[0];
  if(uf) fd.append('file', uf);
  const cf = document.getElementById('cookies').files[0];
  if(cf) fd.append('cookies', cf);
  fd.append('dest', document.getElementById('dest').value.trim() || 'downloads');
  fd.append('audio', document.getElementById('audio').checked ? '1' : '');

  const btn = document.getElementById('submitBtn');
  btn.disabled = true; btn.textContent = 'Queueing…';
  try{
    const r = await fetch('/api/download', {method:'POST', body:fd});
    const data = await r.json();
    if(!r.ok){ toast('Error: ' + (data.error||'failed')); }
    else{
      toast('Added job #' + data.id);
      document.getElementById('urls').value = '';
      document.getElementById('file').value = '';
      document.getElementById('cookies').value = '';
      refreshJobs();
    }
  }catch(e){ toast('Network error'); }
  btn.disabled = false; btn.textContent = '⬇  Download';
});

loadFiles();
refreshJobs();
setInterval(refreshJobs, 1500);
setInterval(loadFiles, 5000);
</script>
</body>
</html>
"""


class LogWriter(io.StringIO):
    def __init__(self, job):
        super().__init__()
        self.job = job

    def write(self, s):
        with JOB_LOCK:
            self.job["log"] += s
            if len(self.job["log"]) > 20000:
                self.job["log"] = self.job["log"][-20000:]
        return len(s)

    def flush(self):
        pass


def _run_job(job_id, url, dest, cookies_path, audio):
    job = JOBS[job_id]
    old_stdout, old_stderr = sys.stdout, sys.stderr
    writer = LogWriter(job)
    sys.stdout, sys.stderr = writer, writer
    prev = os.getcwd()
    try:
        os.chdir(BASE_DIR)
        # Re-import inside the worker so stdout capture is fresh
        import importlib
        import download_media as dm
        importlib.reload(dm)
        argv = ["download_media.py"]
        if cookies_path:
            argv += ["--cookies", cookies_path]
        if audio:
            argv += ["--audio", "mp3"]
        argv += ["--dest", dest, url]
        sys.argv = argv
        with JOB_LOCK:
            job["status"] = "running"
        dm.main()
        with JOB_LOCK:
            job["status"] = "done"
    except SystemExit:
        with JOB_LOCK:
            job["status"] = "done"
    except Exception as e:
        with JOB_LOCK:
            job["status"] = "error"
            job["log"] += f"\n[error] {e}\n"
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr
        os.chdir(prev)


def _worker(job_id, url, dest, cookies_path, audio):
    try:
        _run_job(job_id, url, dest, cookies_path, audio)
    finally:
        with JOB_LOCK:
            job = JOBS.get(job_id)
            if job:
                job["running_thread"] = None


def _save_cookies(req_file):
    os.makedirs(COOKIES_DIR, exist_ok=True)
    import uuid
    fname = f"cookies_{uuid.uuid4().hex[:8]}.txt"
    path = os.path.join(COOKIES_DIR, fname)
    f = req_file
    data = f.read()
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(data)
    return path


def _collect_urls(form):
    urls = []
    for line in (form.get("urls") or "").splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "//")):
            urls.append(line)
    uf = form.get("file")
    if uf and uf.filename:
        raw = uf.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        for line in raw.splitlines():
            line = line.strip()
            if line and not line.startswith(("#", "//")):
                urls.append(line)
    return urls


@app.route("/")
def index():
    return render_template_string(PAGE, default_dest=DEFAULT_DEST)


@app.route("/api/download", methods=["POST"])
def api_download():
    global JOB_COUNTER
    form = request.form
    urls = _collect_urls(form)
    if not urls:
        return jsonify({"error": "No URLs provided."}), 400

    cookies_path = None
    cf = request.files.get("cookies")
    if cf and cf.filename:
        cookies_path = _save_cookies(cf)

    dest = (form.get("dest") or "downloads").strip()
    if not os.path.isabs(dest):
        dest = os.path.join(BASE_DIR, dest)
    os.makedirs(dest, exist_ok=True)

    audio = bool(form.get("audio"))

    first_id = None
    for url in urls:
        with JOB_LOCK:
            JOB_COUNTER += 1
            job_id = JOB_COUNTER
            JOBS[job_id] = {
                "id": job_id,
                "url": url,
                "status": "pending",
                "log": f"Queued: {url}\n",
                "running_thread": None,
            }
        if first_id is None:
            first_id = job_id
        t = threading.Thread(
            target=_worker,
            args=(job_id, url, dest, cookies_path, audio),
            daemon=True,
        )
        with JOB_LOCK:
            JOBS[job_id]["running_thread"] = t
        t.start()

    return jsonify({"id": first_id, "queued": len(urls)})


@app.route("/api/jobs")
def api_jobs():
    with JOB_LOCK:
        jobs = [
            {"id": j["id"], "url": j["url"], "status": j["status"], "log": j["log"]}
            for j in sorted(JOBS.values(), key=lambda x: x["id"])
        ]
    return jsonify(jobs)


@app.route("/api/files")
def api_files():
    dest = request.args.get("dest", DEFAULT_DEST)
    files = []
    if os.path.isdir(dest):
        for name in sorted(os.listdir(dest)):
            full = os.path.join(dest, name)
            if os.path.isfile(full):
                files.append({"name": name, "size": os.path.getsize(full)})
    return jsonify({"files": files[::-1]})


@app.route("/files/<path:name>")
def files_download(name):
    return send_from_directory(DEFAULT_DEST, name, as_attachment=True)


if __name__ == "__main__":
    os.makedirs(DEFAULT_DEST, exist_ok=True)
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"\n➤ Media Downloader UI running at http://{host}:{port}\n")
    app.run(host=host, port=port, debug=False, threaded=True)
