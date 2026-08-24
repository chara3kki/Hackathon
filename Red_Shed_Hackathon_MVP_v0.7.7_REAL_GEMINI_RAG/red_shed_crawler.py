from __future__ import annotations

import io
import json
import os
import re
import time
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag, parse_qsl, urlencode
from urllib import robotparser
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
INDEX_FILE = ROOT / "redshed_site_index.json"
BOOTSTRAP_FILE = ROOT / "redshed_bootstrap_index.json"
EXTERNAL_CANDIDATES_FILE = ROOT / "external_link_candidates.json"

PRIMARY_SITE = "https://redshed.org.au/"
PRIMARY_HOST = "redshed.org.au"

# Optional separately hosted Red Shed-owned sites.
# Example:
# REDSHED_EXTRA_SITES=https://portal.redshed-example.org/,https://another-redshed-site.au/
EXTRA_SITES = [x.strip().rstrip("/") + "/" for x in os.getenv("REDSHED_EXTRA_SITES", "").split(",") if x.strip()]
SITE_ROOTS = [PRIMARY_SITE] + EXTRA_SITES

USER_AGENT = "RedShed-IsRowingForMe-Hackathon/0.7 (+public-website-knowledge-index)"
MAX_PAGES = int(os.getenv("REDSHED_MAX_PAGES", "600"))
MIN_SUCCESSFUL_REFRESH_PAGES = max(1, int(os.getenv("REDSHED_MIN_SUCCESSFUL_REFRESH_PAGES", "5")))
REQUEST_TIMEOUT = 15
CRAWL_DELAY = float(os.getenv("REDSHED_CRAWL_DELAY", "0.12"))
MAX_PDF_BYTES = 18 * 1024 * 1024
CHUNK_CHARS = 2600

SKIP_EXTENSIONS = {
    ".jpg",".jpeg",".png",".gif",".webp",".svg",".ico",".mp4",".mov",".avi",".zip",
    ".doc",".docx",".xls",".xlsx",".ppt",".pptx",".css",".js",".woff",".woff2",".ttf"
}
SKIP_PATH_PARTS = (
    "/wp-admin/","/wp-login","/wp-json/","/xmlrpc.php","/feed/","/comments/feed/",
    "/cart/","/checkout/","/my-account/"
)

INDEX_STATE = {
    "indexing": False,
    "indexed_pages": 0,
    "started_at": None,
    "finished_at": None,
    "error": None,
    "current_url": None,
}
_STATE_LOCK = threading.Lock()


def set_state(**kwargs):
    with _STATE_LOCK:
        INDEX_STATE.update(kwargs)


def get_state():
    with _STATE_LOCK:
        return dict(INDEX_STATE)


def normalise_host(host: str) -> str:
    return (host or "").lower().split(":")[0].removeprefix("www.")


def extra_root_hosts() -> set[str]:
    return {
        normalise_host(urlparse(root).netloc)
        for root in EXTRA_SITES
        if urlparse(root).netloc
    }


def host_is_allowed(host: str) -> bool:
    """Allow redshed.org.au and ALL of its subdomains automatically.
    Separately hosted official Red Shed sites must be explicitly allow-listed.
    """
    host = normalise_host(host)
    if host == PRIMARY_HOST or host.endswith("." + PRIMARY_HOST):
        return True

    for root_host in extra_root_hosts():
        if host == root_host or host.endswith("." + root_host):
            return True

    return False


def canonicalize(url: str) -> str | None:
    try:
        url = urldefrag(url)[0]
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return None
        if not host_is_allowed(p.netloc):
            return None

        kept = []
        for k, v in parse_qsl(p.query, keep_blank_values=True):
            if k.lower().startswith(("utm_", "gad_", "gclid", "gbraid", "fbclid")):
                continue
            kept.append((k, v))
        query = urlencode(kept)

        path = re.sub(r"/{2,}", "/", p.path or "/")
        if not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
            path += "/"

        host = p.netloc
        return f"https://{host}{path}" + (f"?{query}" if query else "")
    except Exception:
        return None


def allowed_url(url: str) -> bool:
    p = urlparse(url)
    if not host_is_allowed(p.netloc):
        return False

    lower = p.path.lower()
    if any(part in lower for part in SKIP_PATH_PARTS):
        return False

    suffix = Path(lower).suffix
    if suffix in SKIP_EXTENSIONS:
        return False

    return True


def clean_text(text: str) -> str:
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int = CHUNK_CHARS) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, current = [], ""

    for p in paras:
        if len(current) + len(p) + 2 <= size:
            current = (current + "\n\n" + p).strip()
        else:
            if current:
                chunks.append(current)

            if len(p) <= size:
                current = p
            else:
                for i in range(0, len(p), size):
                    part = p[i:i + size]
                    if len(part) == size:
                        chunks.append(part)
                    else:
                        current = part

    if current:
        chunks.append(current)
    return chunks


def parse_html(url: str, html: str):
    soup = BeautifulSoup(html, "html.parser")

    # Save all links before stripping navigation.
    discovered_allowed = []
    external_candidates = []

    for a in soup.find_all("a", href=True):
        raw = urljoin(url, a["href"])
        p = urlparse(raw)

        if p.scheme not in ("http", "https"):
            continue

        if host_is_allowed(p.netloc):
            c = canonicalize(raw)
            if c and allowed_url(c):
                discovered_allowed.append(c)
        else:
            host = normalise_host(p.netloc)
            if host:
                external_candidates.append({
                    "host": host,
                    "url": urldefrag(raw)[0],
                    "anchor": clean_text(a.get_text(" ", strip=True))[:160],
                    "found_on": url,
                })

    for tag in soup(["script", "style", "noscript", "svg", "form"]):
        tag.decompose()

    title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else url
    main = soup.find("main") or soup.find("article") or soup.body or soup

    # Navigation/footer are useful for discovery but repetitive as AI context.
    for tag in main.find_all(["nav", "footer", "header"]):
        tag.decompose()

    text = clean_text(main.get_text("\n", strip=True))

    return (
        title,
        text,
        list(dict.fromkeys(discovered_allowed)),
        external_candidates,
    )


def parse_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    parts = []

    for page in reader.pages[:150]:
        try:
            txt = page.extract_text() or ""
            if txt.strip():
                parts.append(txt)
        except Exception:
            continue

    return clean_text("\n\n".join(parts))


def load_robots(session: requests.Session, site_root: str):
    rp = robotparser.RobotFileParser()
    robots_url = urljoin(site_root, "robots.txt")
    rp.set_url(robots_url)
    sitemaps = []

    try:
        r = session.get(robots_url, timeout=REQUEST_TIMEOUT)
        if r.ok:
            lines = r.text.splitlines()
            rp.parse(lines)

            for line in lines:
                if line.lower().startswith("sitemap:"):
                    candidate = line.split(":", 1)[1].strip()
                    if candidate:
                        sitemaps.append(candidate)

            return rp, sitemaps
    except Exception:
        pass

    return None, sitemaps


def discover_sitemap_urls(session: requests.Session, site_root: str, robots_sitemaps=None) -> list[str]:
    found = []
    candidates = list(robots_sitemaps or [])
    candidates += [
        urljoin(site_root, "wp-sitemap.xml"),
        urljoin(site_root, "sitemap_index.xml"),
        urljoin(site_root, "sitemap.xml"),
    ]

    seen_xml = set()
    queue = deque(dict.fromkeys(candidates))

    while queue and len(seen_xml) < 50:
        sm_url = queue.popleft()
        if sm_url in seen_xml:
            continue
        seen_xml.add(sm_url)

        try:
            r = session.get(sm_url, timeout=REQUEST_TIMEOUT)
            if r.status_code != 200 or "<" not in r.text[:300]:
                continue

            root = ET.fromstring(r.content)
            locs = [
                el.text.strip()
                for el in root.iter()
                if el.tag.endswith("loc") and el.text
            ]

            for loc in locs:
                if loc.lower().endswith(".xml"):
                    queue.append(loc)
                else:
                    c = canonicalize(loc)
                    if c and allowed_url(c):
                        found.append(c)
        except Exception:
            continue

    return list(dict.fromkeys(found))


def crawl_site(progress_callback=None) -> dict:
    set_state(
        indexing=True,
        indexed_pages=0,
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=None,
        error=None,
        current_url=None,
    )

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.5",
    })

    # Build robots rules + sitemap discovery for each configured root.
    robots_by_host = {}
    sitemap_seeds = []

    for root in SITE_ROOTS:
        host = normalise_host(urlparse(root).netloc)
        rp, robot_sitemaps = load_robots(session, root)
        robots_by_host[host] = rp
        sitemap_seeds += discover_sitemap_urls(session, root, robot_sitemaps)

    # High-value Red Shed starting pages + sitemap results.
    seeds = [
        PRIMARY_SITE,
        urljoin(PRIMARY_SITE, "get-started/"),
        urljoin(PRIMARY_SITE, "row/"),
        urljoin(PRIMARY_SITE, "learn-to-row/"),
        urljoin(PRIMARY_SITE, "continuing-to-row/"),
        urljoin(PRIMARY_SITE, "camps-and-clinics/"),
        urljoin(PRIMARY_SITE, "youth-school-programs/"),
        urljoin(PRIMARY_SITE, "programs/"),
        urljoin(PRIMARY_SITE, "train/"),
        urljoin(PRIMARY_SITE, "recover/"),
        urljoin(PRIMARY_SITE, "connect/"),
        urljoin(PRIMARY_SITE, "easy-oar/"),
        urljoin(PRIMARY_SITE, "about/"),
        urljoin(PRIMARY_SITE, "about/faqs/"),
        urljoin(PRIMARY_SITE, "hours/"),
        urljoin(PRIMARY_SITE, "starter-pack/"),
        urljoin(PRIMARY_SITE, "visit/"),
        urljoin(PRIMARY_SITE, "red-shedder-membership/"),
        urljoin(PRIMARY_SITE, "contact/"),
    ]
    seeds += SITE_ROOTS
    seeds += sitemap_seeds

    queue = deque(
        dict.fromkeys(canonicalize(u) for u in seeds if canonicalize(u))
    )
    seen = set()
    pages = []
    external_candidates = []

    while queue and len(seen) < MAX_PAGES:
        url = queue.popleft()

        if not url or url in seen or not allowed_url(url):
            continue

        host = normalise_host(urlparse(url).netloc)
        rp = robots_by_host.get(host)

        # A newly discovered subdomain may not have a parser yet.
        if host not in robots_by_host:
            root = f"https://{host}/"
            rp, robot_sitemaps = load_robots(session, root)
            robots_by_host[host] = rp

            for sm_url in discover_sitemap_urls(session, root, robot_sitemaps):
                if sm_url not in seen:
                    queue.append(sm_url)

        if rp is not None:
            try:
                if not rp.can_fetch(USER_AGENT, url):
                    continue
            except Exception:
                pass

        seen.add(url)
        set_state(current_url=url)

        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)

            # Only retain redirects that remain on an allowed official host.
            if not host_is_allowed(urlparse(r.url).netloc):
                continue

            final_url = canonicalize(r.url) or url
            ctype = (r.headers.get("content-type") or "").lower()

            if r.status_code != 200:
                continue

            if "application/pdf" in ctype or final_url.lower().endswith(".pdf"):
                if len(r.content) > MAX_PDF_BYTES:
                    continue

                text = parse_pdf(r.content)
                if not text:
                    continue

                title = Path(urlparse(final_url).path).name or "Red Shed PDF"
                links = []
                external = []
                kind = "pdf"

            elif "text/html" in ctype or "application/xhtml" in ctype or not ctype:
                title, text, links, external = parse_html(final_url, r.text)
                external_candidates.extend(external)

                if len(text) < 80:
                    continue

                kind = "html"

                for link in links:
                    if link not in seen:
                        queue.append(link)

            else:
                continue

            pages.append({
                "url": final_url,
                "title": title,
                "kind": kind,
                "host": normalise_host(urlparse(final_url).netloc),
                "text": text,
                "chunks": chunk_text(text),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })

            set_state(indexed_pages=len(pages))

            if progress_callback:
                progress_callback(len(pages), final_url)

            time.sleep(CRAWL_DELAY)

        except Exception:
            continue

    hosts = sorted({p["host"] for p in pages})

    completed_at = datetime.now(timezone.utc).isoformat()
    data = {
        "site_roots": SITE_ROOTS,
        "generated_at": completed_at,
        "snapshot_at": completed_at,
        "source_mode": "live_website",
        "count": len(pages),
        "hosts": hosts,
        "pages": pages,
    }

    # Never destroy a known-good index because the website, Wi-Fi, DNS,
    # robots rules, or a temporary request failed during this refresh.
    previous = install_bootstrap_if_needed()
    previous_count = int(previous.get("count", 0))

    if len(pages) < MIN_SUCCESSFUL_REFRESH_PAGES and previous_count >= len(pages):
        set_state(
            indexing=False,
            indexed_pages=previous_count,
            finished_at=completed_at,
            error=(
                f"Live refresh returned only {len(pages)} usable page(s); "
                f"kept the previous {previous_count}-item knowledge snapshot."
            ),
            current_url=None,
        )
        return previous

    tmp = INDEX_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(INDEX_FILE)

    # Keep a deduplicated list of external domains linked from Red Shed.
    # These are NOT automatically trusted/crawled.
    seen_ext = set()
    compact_ext = []
    for item in external_candidates:
        key = (item["host"], item["url"])
        if key in seen_ext:
            continue
        seen_ext.add(key)
        compact_ext.append(item)

    EXTERNAL_CANDIDATES_FILE.write_text(
        json.dumps(compact_ext[:1500], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    set_state(
        indexing=False,
        indexed_pages=len(pages),
        finished_at=data["generated_at"],
        error=None,
        current_url=None,
    )

    return data


def run_background_refresh():
    if get_state().get("indexing"):
        return False

    def runner():
        try:
            crawl_site()
        except Exception as exc:
            set_state(
                indexing=False,
                error=str(exc),
                finished_at=datetime.now(timezone.utc).isoformat(),
                current_url=None,
            )

    threading.Thread(target=runner, daemon=True).start()
    return True



def _empty_index() -> dict:
    return {
        "count": 0,
        "pages": [],
        "generated_at": None,
        "snapshot_at": None,
        "source_mode": "empty",
        "site_roots": SITE_ROOTS,
        "hosts": [],
    }


def load_bootstrap_index() -> dict:
    if not BOOTSTRAP_FILE.exists():
        return _empty_index()
    try:
        data = json.loads(BOOTSTRAP_FILE.read_text(encoding="utf-8"))
        if int(data.get("count", 0)) > 0 and data.get("pages"):
            return data
    except Exception:
        pass
    return _empty_index()


def install_bootstrap_if_needed() -> dict:
    """Guarantee a usable knowledge index before the live crawl finishes."""
    current = _empty_index()

    if INDEX_FILE.exists():
        try:
            current = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            if int(current.get("count", 0)) > 0 and current.get("pages"):
                set_state(indexed_pages=int(current.get("count", 0)))
                return current
        except Exception:
            pass

    bootstrap = load_bootstrap_index()
    if int(bootstrap.get("count", 0)) > 0:
        try:
            tmp = INDEX_FILE.with_suffix(".json.bootstrap.tmp")
            tmp.write_text(json.dumps(bootstrap, ensure_ascii=False), encoding="utf-8")
            tmp.replace(INDEX_FILE)
        except Exception:
            # Even if the runtime cannot write, return the in-memory snapshot.
            pass
        set_state(indexed_pages=int(bootstrap.get("count", 0)))
        return bootstrap

    return _empty_index()


def load_index() -> dict:
    if not INDEX_FILE.exists():
        return install_bootstrap_if_needed()

    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        if int(data.get("count", 0)) <= 0 or not data.get("pages"):
            return install_bootstrap_if_needed()
        set_state(indexed_pages=int(data.get("count", 0)))
        return data
    except Exception:
        return install_bootstrap_if_needed()


STOPWORDS = set("""
the a an and or but if then than to of in on at for with from by as is are was were be been being
it its this that these those i you your we our they their me my can could would should do does did
about what which who when where why how red shed
""".split())


def tokens(s: str):
    return [
        w
        for w in re.findall(r"[a-z0-9']+", s.lower())
        if len(w) > 2 and w not in STOPWORDS
    ]


def retrieve(query: str, k: int = 10):
    data = load_index()
    qtokens = tokens(query)
    qset = set(qtokens)

    if not qset:
        return []

    scored = []

    for page in data.get("pages", []):
        title_tokens = set(tokens(page.get("title", "")))
        url_tokens = set(tokens(page.get("url", "")))

        for idx, chunk in enumerate(page.get("chunks", [])):
            ctokens = tokens(chunk)
            cset = set(ctokens)
            overlap = qset & cset

            if not overlap:
                continue

            score = sum(min(ctokens.count(t), 4) for t in overlap)
            score += 5 * len(qset & title_tokens)
            score += 3 * len(qset & url_tokens)

            phrase = query.lower().strip()
            if len(phrase) > 8 and phrase in chunk.lower():
                score += 12

            scored.append({
                "score": score,
                "url": page["url"],
                "title": page.get("title") or page["url"],
                "host": page.get("host") or normalise_host(urlparse(page["url"]).netloc),
                "chunk": chunk,
                "chunk_index": idx,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)

    out, per_page = [], {}

    for item in scored:
        n = per_page.get(item["url"], 0)
        if n >= 3:
            continue

        out.append(item)
        per_page[item["url"]] = n + 1

        if len(out) >= k:
            break

    return out


if __name__ == "__main__":
    def progress(n, url):
        print(f"[{n:03d}] {url}")

    data = crawl_site(progress)

    print(f"\nIndexed {data['count']} public Red Shed pages/documents.")
    print("Hosts:", ", ".join(data.get("hosts", [])) or "none")
    print(f"Saved to: {INDEX_FILE}")
