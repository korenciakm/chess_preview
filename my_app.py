import html
import urllib.parse
import chess
import chess.svg
import resvg_py
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

app = FastAPI(title="Lichess FEN Preview")


def parse_fen(raw_fen: str) -> chess.Board:
    decoded = urllib.parse.unquote(raw_fen).strip()
    normalized = decoded.replace("_", " ")
    return chess.Board(normalized)


def get_public_base_url(request: Request) -> str:
    base_url = str(request.base_url).rstrip("/")
    # Cloud Run terminates TLS at Google Front End and forwards X-Forwarded-Proto
    if request.headers.get("x-forwarded-proto") == "https" and base_url.startswith("http://"):
        base_url = "https://" + base_url[len("http://"):]
    return base_url


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    base_url = get_public_base_url(request)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FEN Preview Link Generator</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 640px; margin: 48px auto; padding: 0 16px; }}
    input {{ width: 100%; padding: 10px; font-size: 15px; margin: 10px 0; box-sizing: border-box; }}
    button {{ padding: 10px 16px; font-size: 15px; cursor: pointer; }}
    .out {{ margin-top: 16px; word-break: break-all; background: #f4f4f5; padding: 12px; border-radius: 6px; }}
  </style>
</head>
<body>
  <h2>Lichess FEN Preview Link Generator</h2>
  <input id="fen" type="text" placeholder="Paste FEN (e.g. rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1)">
  <button onclick="generateLink()">Generate &amp; Copy Link</button>
  <div id="result" class="out" style="display:none;"></div>
  <script>
    function generateLink() {{
      const raw = document.getElementById('fen').value.trim();
      if (!raw) return;
      const slug = raw.replace(/\\s+/g, '_');
      const link = `{base_url}/p/` + slug;
      navigator.clipboard?.writeText(link);
      const box = document.getElementById('result');
      box.style.display = 'block';
      box.innerHTML = `<strong>Copied to clipboard:</strong><br><a href="${{link}}">${{link}}</a>`;
    }}
  </script>
</body>
</html>"""


@app.get("/img/{fen_path:path}")
async def render_board_png(fen_path: str):
    try:
        board = parse_fen(fen_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN string")

    svg_data = chess.svg.board(
        board=board,
        orientation=board.turn,
        size=480,
    )
    png_bytes = resvg_py.svg_to_bytes(svg_string=svg_data)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/p/{fen_path:path}", response_class=HTMLResponse)
async def preview_and_redirect(fen_path: str, request: Request):
    try:
        board = parse_fen(fen_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN string")

    clean_fen = board.fen()
    slug = clean_fen.replace(" ", "_")
    base_url = get_public_base_url(request)

    image_url = f"{base_url}/img/{slug}"
    lichess_url = f"https://lichess.org/analysis/standard/{slug}"

    turn_label = "White to move" if board.turn == chess.WHITE else "Black to move"
    title = f"Chess Position ({turn_label})"
    description = f"FEN: {clean_fen} — Click to analyze on Lichess.org"

    safe_title = html.escape(title)
    safe_desc = html.escape(description)
    safe_img = html.escape(image_url)
    safe_target = html.escape(lichess_url)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{safe_title}</title>

  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Lichess FEN Preview">
  <meta property="og:title" content="{safe_title}">
  <meta property="og:description" content="{safe_desc}">
  <meta property="og:image" content="{safe_img}">
  <meta property="og:image:type" content="image/png">
  <meta property="og:image:width" content="480">
  <meta property="og:image:height" content="480">
  <meta name="twitter:card" content="summary_large_image">

  <meta http-equiv="refresh" content="0;url={safe_target}">
  <script>window.location.replace({lichess_url!r});</script>
</head>
<body>
  <p>Redirecting to <a href="{safe_target}">Lichess.org</a>...</p>
</body>
</html>"""