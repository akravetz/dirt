"""Tiny web server to listen through a directory of WAVs.

Serves an HTML page that lists every .wav in the given directory with an
HTML5 <audio> player. Keyboard nav: Up/Down (or j/k) for prev/next, space to
play current, r to replay from start. Useful for quickly triaging captured
audio (positives vs negatives, good vs garbage) without launching a full DAW.

Usage:
    uv run python scripts/audio-review.py <dir> [--port 8080]
    uv run python scripts/audio-review.py var/wake-word/realmic-stage/<TS>/
"""

from __future__ import annotations

import argparse
import http.server
import sys
from pathlib import Path

INDEX_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>__TITLE__</title>
<style>
  body { font: 14px ui-monospace, "SF Mono", Menlo, monospace; padding: 20px; max-width: 1100px; margin: auto; color: #222; }
  h1 { font-size: 16px; font-weight: 600; word-break: break-all; }
  .meta { color: #888; margin-bottom: 16px; }
  .row { display: flex; align-items: center; padding: 6px 8px; gap: 12px; border-radius: 4px; }
  .row.current { background: #fff5b8; }
  .row .idx { color: #888; min-width: 36px; text-align: right; }
  .row .name { flex: 1; word-break: break-all; }
  audio { height: 32px; width: 320px; }
  .help { position: fixed; top: 12px; right: 12px; padding: 8px 12px; background: white; border: 1px solid #ccc; border-radius: 4px; font-size: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); }
  kbd { font-family: ui-monospace, monospace; background: #eee; padding: 1px 5px; border-radius: 3px; }
  .empty { color: #888; font-style: italic; padding: 24px 0; }
</style></head><body>
<div class="help">
  <kbd>↑</kbd>/<kbd>↓</kbd> nav · <kbd>space</kbd> play · <kbd>r</kbd> replay
</div>
<h1>__TITLE__</h1>
<div class="meta">__N__ files</div>
<div id="list">
__ROWS__
</div>
<script>
let idx = 0;
const rows = document.querySelectorAll('.row');
function highlight() {
  rows.forEach((r, i) => r.classList.toggle('current', i === idx));
  if (rows[idx]) rows[idx].scrollIntoView({block: 'center', behavior: 'smooth'});
}
function play() {
  rows.forEach((r, i) => {
    const a = r.querySelector('audio');
    if (i === idx) { a.currentTime = 0; a.play(); }
    else { a.pause(); a.currentTime = 0; }
  });
}
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'ArrowDown' || e.key === 'j') {
    idx = Math.min(rows.length - 1, idx + 1); highlight(); play(); e.preventDefault();
  } else if (e.key === 'ArrowUp' || e.key === 'k') {
    idx = Math.max(0, idx - 1); highlight(); play(); e.preventDefault();
  } else if (e.key === ' ') {
    const a = rows[idx] && rows[idx].querySelector('audio');
    if (a) { a.currentTime = 0; a.play(); }
    e.preventDefault();
  } else if (e.key === 'r' || e.key === 'R') {
    const a = rows[idx] && rows[idx].querySelector('audio');
    if (a) { a.currentTime = 0; a.play(); }
  }
});
highlight();
</script>
</body></html>
"""


def make_handler(audio_dir: Path):
    audio_dir_str = str(audio_dir)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=audio_dir_str, **kwargs)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send_index()
                return
            super().do_GET()

        def log_message(self, fmt, *args):
            # Quieter than the default access log
            sys.stderr.write(f"[audio-review] {fmt % args}\n")

        def _send_index(self):
            wavs = sorted(audio_dir.glob("*.wav"))
            if not wavs:
                rows = '<div class="empty">No .wav files in this directory.</div>'
            else:
                rows = "\n".join(
                    f'<div class="row" data-idx="{i}">'
                    f'<span class="idx">{i + 1:03d}</span>'
                    f'<span class="name">{p.name}</span>'
                    f'<audio controls preload="none" src="/{p.name}"></audio>'
                    f"</div>"
                    for i, p in enumerate(wavs)
                )
            html = (
                INDEX_TEMPLATE.replace("__TITLE__", str(audio_dir))
                .replace("__N__", str(len(wavs)))
                .replace("__ROWS__", rows)
            )
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("dir", type=Path, help="Directory of .wav files to review.")
    p.add_argument("--port", type=int, default=8080, help="Port to serve on (default 8080).")
    p.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1).")
    args = p.parse_args()

    if not args.dir.is_dir():
        sys.exit(f"Not a directory: {args.dir}")

    handler = make_handler(args.dir.resolve())
    n = sum(1 for _ in args.dir.glob("*.wav"))
    print(f"audio-review · {args.dir} · {n} WAVs")
    print(f"  → http://{args.host}:{args.port}")
    print("  Ctrl-C to stop")
    server = http.server.ThreadingHTTPServer((args.host, args.port), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    server.server_close()


if __name__ == "__main__":
    main()
