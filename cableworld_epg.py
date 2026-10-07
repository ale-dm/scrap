#!/usr/bin/env python3
"""Scraper de la parrilla de Cableworld Crevillent -> XMLTV para Dispatcharr.

Solo usa la librería estándar. Modos:
  python cableworld_epg.py -o epg.xml            # genera una vez
  python cableworld_epg.py --serve               # regenera cada N horas y sirve el XML por HTTP
"""
import argparse
import http.server
import os
import re
import sys
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from html.parser import HTMLParser
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

DEFAULT_URL = "https://hlsnov.cableworld.es/"
TZ = ZoneInfo("Europe/Madrid")
DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")


class _GridParser(HTMLParser):
    """Recorre la tabla: td.fecha = cabecera de día, td.hora + td siguiente = programa."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []  # ("fecha", texto) | ("hora", texto) | ("titulo", texto)
        self._cls = None
        self._buf = None

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self._cls = dict(attrs).get("class") or "titulo"
            self._buf = []

    def handle_data(self, data):
        if self._buf is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self._buf is not None:
            text = " ".join("".join(self._buf).split())
            self.rows.append((self._cls, text))
            self._buf = None


def parse_schedule(html):
    """Devuelve lista de (inicio datetime con tz, título) ordenada."""
    parser = _GridParser()
    parser.feed(html)
    day = None
    pending_time = None
    items = []
    for kind, text in parser.rows:
        if kind == "fecha":
            m = DATE_RE.search(text)
            if m:
                d, mo, y = map(int, m.groups())
                day = datetime(y, mo, d)
            pending_time = None
        elif kind == "hora" and day is not None:
            m = TIME_RE.match(text)
            pending_time = (
                day.replace(hour=int(m[1]), minute=int(m[2]), second=int(m[3] or 0), tzinfo=TZ)
                if m else None
            )
        elif kind == "titulo" and pending_time is not None and text:
            items.append((pending_time, text))
            pending_time = None
    items.sort(key=lambda x: x[0])
    # descarta duplicados exactos de hora de inicio
    uniq, seen = [], set()
    for start, title in items:
        if start not in seen:
            seen.add(start)
            uniq.append((start, title))
    return uniq


def build_xmltv(items, channel_id, channel_name, last_minutes=60, logo=None):
    fmt = "%Y%m%d%H%M%S %z"
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<tv generator-info-name="cableworld-epg">',
           f'  <channel id="{escape(channel_id)}">',
           f'    <display-name lang="es">{escape(channel_name)}</display-name>']
    if logo:
        out.append(f'    <icon src="{escape(logo)}"/>')
    out.append("  </channel>")
    for i, (start, title) in enumerate(items):
        stop = items[i + 1][0] if i + 1 < len(items) else start + timedelta(minutes=last_minutes)
        out.append(
            f'  <programme start="{start.strftime(fmt)}" stop="{stop.strftime(fmt)}" '
            f'channel="{escape(channel_id)}">'
        )
        out.append(f'    <title lang="es">{escape(title)}</title>')
        out.append("  </programme>")
    out.append("</tv>")
    return "\n".join(out) + "\n"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "cableworld-epg/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def generate(args):
    html = open(args.input, encoding="utf-8").read() if args.input else fetch(args.url)
    items = parse_schedule(html)
    if not items:
        raise RuntimeError("No se encontró ningún programa: ¿ha cambiado el formato de la web?")
    xml = build_xmltv(items, args.channel_id, args.channel_name, args.last_minutes, args.logo)
    tmp = args.output + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(xml)
    os.replace(tmp, args.output)  # escritura atómica: Dispatcharr nunca lee un XML a medias
    print(f"{datetime.now():%F %T} OK: {len(items)} programas -> {args.output}", flush=True)


def serve(args):
    directory = os.path.dirname(os.path.abspath(args.output)) or "."

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=directory, **kw)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"Sirviendo {os.path.basename(args.output)} en :{args.port}", flush=True)
    while True:
        try:
            generate(args)
        except Exception as e:  # mantiene el último XML bueno si falla la web
            print(f"ERROR: {e}", file=sys.stderr, flush=True)
        time.sleep(args.interval * 3600)


def main():
    env = os.environ.get
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--url", default=env("EPG_URL", DEFAULT_URL))
    p.add_argument("--input", help="HTML local en vez de descargar (pruebas)")
    p.add_argument("-o", "--output", default=env("EPG_OUTPUT", "epg.xml"))
    p.add_argument("--channel-id", default=env("CHANNEL_ID", "Telecrevillent"),
                   help="debe coincidir con el tvg-id del m3u")
    p.add_argument("--channel-name", default=env("CHANNEL_NAME", "Telecrevillent"))
    p.add_argument("--logo", default=env("CHANNEL_LOGO", "https://hlsnov.cableworld.es/logo.png"))
    p.add_argument("--last-minutes", type=int, default=int(env("LAST_MINUTES", "60")),
                   help="duración asumida del último programa (la web no da hora de fin)")
    p.add_argument("--serve", action="store_true")
    p.add_argument("--port", type=int, default=int(env("PORT", "8080")))
    p.add_argument("--interval", type=float, default=float(env("INTERVAL_HOURS", "12")))
    args = p.parse_args()
    serve(args) if args.serve else generate(args)


if __name__ == "__main__":
    main()
