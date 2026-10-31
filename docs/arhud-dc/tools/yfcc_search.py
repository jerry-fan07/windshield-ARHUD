#!/usr/bin/env python3
"""Search the YFCC100M Creative Commons videos (Multimedia Commons on S3) for footage by title, description and tags.

The only searchable metadata in the bucket is one 65 GB SQLite file (tools/etc/yfcc100m_dataset.sql). It is never
stored: it is streamed in parallel byte ranges, each 1 KiB b-tree leaf page whose bytes match the keywords is parsed
in place (cells, records, overflow chains fetched on demand), and only video rows (marker = 1) are kept.

    python3 tools/yfcc_search.py out.jsonl                 # whole file, ~65 GB through the network
    python3 tools/yfcc_search.py out.jsonl --local head.part  # parse a local slice instead (testing)

Each hit: photoid, title, description, tags, capture device, licence, Flickr page and the video's mp4 URL on S3.
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import re
import struct
import subprocess
import sys
import urllib.parse
import urllib.request

DB = "https://multimedia-commons.s3.amazonaws.com/tools/etc/yfcc100m_dataset.sql"
MP4 = "https://multimedia-commons.s3.amazonaws.com/data/videos/mp4/"
PAGE = 1024
COLS = ["photoid", "uid", "unickname", "datetaken", "dateuploaded", "capturedevice", "title", "description",
        "usertags", "machinetags", "longitude", "latitude", "accuracy", "pageurl", "downloadurl", "licensename",
        "licenseurl", "serverid", "farmid", "secret", "secretoriginal", "ext", "marker"]
# URL-encoded the way YFCC stores text ('+' for spaces). GNU grep finds candidate pages (fast); Python re confirms.
GREP = r"datacent|data\+cent|server\+?room|server\+?rack|patch\+?panel|patch\+?cord|patch\+?cable|cable\+manag|" \
       r"cabling|colocation|network\+rack|network\+cabinet|wiring\+closet|network\+closet|punch\+?down|cross\+?connect|" \
       r"fib(er|re)\+optic|rack\+and\+stack|serverraum|rechenzentrum|centro\+de\+datos|centre\+de\+donn"
KEYWORDS = ("(?i)" + GREP).encode()


def varint(b, i):
    v = 0
    for k in range(9):
        c = b[i + k]
        if k == 8:
            return (v << 8) | c, i + 9
        v = (v << 7) | (c & 0x7F)
        if c < 0x80:
            return v, i + k + 1


def fetch(lo, hi, tries=5):
    for t in range(tries):
        try:
            req = urllib.request.Request(DB, headers={"Range": f"bytes={lo}-{hi - 1}"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception:
            if t == tries - 1:
                raise


def payload(page, off, read_page):
    """Full payload of the table-leaf cell at off (following overflow pages through read_page)."""
    P, i = varint(page, off)
    rowid, i = varint(page, i)
    U = PAGE
    X = U - 35
    if P <= X:
        return rowid, page[i:i + P]
    M = (U - 12) * 32 // 255 - 23
    K = M + (P - M) % (U - 4)
    local = K if K <= X else M
    data = bytearray(page[i:i + local])
    nxt = struct.unpack(">I", page[i + local:i + local + 4])[0]
    while len(data) < P and nxt:
        ov = read_page(nxt)
        nxt = struct.unpack(">I", ov[:4])[0]
        data += ov[4:4 + min(U - 4, P - len(data))]
    return rowid, bytes(data)


def record(rowid, p):
    hs, i = varint(p, 0)
    types = []
    while i < hs:
        t, i = varint(p, i)
        types.append(t)
    vals, j = [], hs
    for t in types:
        if t == 0:
            vals.append(None)
        elif 1 <= t <= 6:
            n = [0, 1, 2, 3, 4, 6, 8][t]
            vals.append(int.from_bytes(p[j:j + n], "big", signed=True))
            j += n
        elif t == 7:
            vals.append(struct.unpack(">d", p[j:j + 8])[0])
            j += 8
        elif t in (8, 9):
            vals.append(t - 8)
        elif t >= 12:
            n = (t - 12) // 2 if t % 2 == 0 else (t - 13) // 2
            vals.append(p[j:j + n].decode("utf-8", "replace"))
            j += n
    if len(vals) != len(COLS):
        return None
    d = dict(zip(COLS, vals))
    d["photoid"] = rowid
    return d


def leaf_cells(page, base):
    if page[base] != 0x0D:
        return []
    n = struct.unpack(">H", page[base + 3:base + 5])[0]
    return [struct.unpack(">H", page[base + 8 + 2 * k:base + 10 + 2 * k])[0] for k in range(n)]


def unq(s):
    return urllib.parse.unquote_plus(s or "")


def grep_offsets(buf):
    r = subprocess.run(["grep", "-boaiE", GREP], input=buf, capture_output=True, env={"LC_ALL": "C"})
    return [int(line.split(b":", 1)[0]) for line in r.stdout.splitlines() if b":" in line]


def scan_chunk(buf, start, read_page, pat):
    hits = {}
    for o in grep_offsets(buf):
        hits[(start + o) // PAGE] = None
    out = []
    for pg in hits:
        off = pg * PAGE - start
        page = buf[off:off + PAGE] if 0 <= off and off + PAGE <= len(buf) else read_page(pg + 1)
        base = 100 if pg == 0 else 0
        for c in leaf_cells(page, base):
            try:
                rowid, p = payload(page, c, read_page)
                if not pat.search(p):
                    continue
                r = record(rowid, p)
            except Exception:
                continue
            if r and r.get("marker") == 1:
                out.append({"photoid": r["photoid"], "title": unq(r["title"]), "description": unq(r["description"])[:600],
                            "tags": unq(r["usertags"]), "device": unq(r["capturedevice"]), "license": r["licensename"],
                            "page": r["pageurl"], "user": unq(r["unickname"]), "taken": r["datetaken"],
                            "mp4": mp4_url(r["downloadurl"] or "")})
    return out


def mp4_url(download_url):
    """Multimedia Commons names each video by the MD5 of its Flickr download URL, each byte as unpadded hex."""
    n = "".join(f"{b:x}" for b in hashlib.md5(download_url.encode()).digest())
    return f"{MP4}{n[:3]}/{n[3:6]}/{n}.mp4"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--local")
    ap.add_argument("--chunk-mb", type=int, default=48)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--start-gb", type=float, default=0.0)
    ap.add_argument("--end-gb", type=float, default=None)
    args = ap.parse_args()
    pat = re.compile(KEYWORDS)
    if args.local:
        buf = open(args.local, "rb").read()

        def rp(n):
            o = (n - 1) * PAGE
            return buf[o:o + PAGE] if o + PAGE <= len(buf) else fetch(o, o + PAGE)
        res = scan_chunk(buf, 0, rp, pat)
        with open(args.out, "w") as f:
            for r in res:
                f.write(json.dumps(r) + "\n")
        print(len(res), "video hits")
        return
    size = 65644027904
    lo0 = int(args.start_gb * 1e9) // PAGE * PAGE
    hi0 = size if args.end_gb is None else min(size, int(args.end_gb * 1e9) // PAGE * PAGE)
    cs = args.chunk_mb * 1024 * 1024
    ranges = [(lo, min(hi0, lo + cs)) for lo in range(lo0, hi0, cs)]

    def rp(n):
        o = (n - 1) * PAGE
        return fetch(o, o + PAGE)

    def work(r):
        buf = fetch(*r)
        return r, scan_chunk(buf, r[0], rp, pat)
    done = 0
    with open(args.out, "a") as f, cf.ThreadPoolExecutor(args.workers) as ex:
        for r, res in ex.map(work, ranges):
            for x in res:
                f.write(json.dumps(x) + "\n")
            f.flush()
            done += 1
            if done % 20 == 0:
                print(f"{done}/{len(ranges)} chunks, at {r[1] / 1e9:.1f} GB", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
