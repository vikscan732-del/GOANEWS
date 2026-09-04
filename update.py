import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

THE_GOAN = [
    {"name":"THE GOAN EVERYDAY","description":"Goa's Leading English Daily Newspaper","language":"English","url":"https://epaper.thegoan.net/edition/THE-GOAN-EVERYDAY/10711","logo":"assets/logos/the-goan-everyday.svg"},
    {"name":"GOAN VARTA","description":"Goa's Leading Marathi Daily Newspaper","language":"Marathi","url":"https://epaper.thegoan.net/edition/GOAN-VARTA/9849","logo":"assets/logos/goan-varta.svg"},
    {"name":"BHAANGARBHUIN","description":"Goa's Konkani Daily Newspaper","language":"Konkani","url":"https://epaper.thegoan.net/edition/BHAANGARBHUIN/23246","logo":"assets/logos/bhaangar-bhuin.svg"},
    {"name":"KONKANSAAD","description":"KONKANSAAD Marathi Newspaper","language":"Marathi","url":"https://epaper.thegoan.net/edition/KONKANSAAD/37473","logo":"assets/logos/konkansaad.svg"},
]

HERALD = [
    {"name":"O HERALDO","description":"Goa's English Daily Newspaper","language":"English","slug":"oheraldo","logo":"assets/logos/o-heraldo.svg"},
    {"name":"DAINIK HERALD","description":"Goa's Marathi Daily Newspaper","language":"Marathi","slug":"dainik-herald","logo":"assets/logos/dainik-herald.svg"},
]

OTHER = [
    {"name":"NAVHIND TIMES","description":"Goa's Trusted English Daily Newspaper","language":"English","url":"https://epaper.navhindtimes.in/mainpage.aspx","logo":"assets/logos/navhind-times.svg"},
    {"name":"LOKMAT (GOA EDITION)","description":"Marathi Daily Newspaper — Goa Edition","language":"Marathi","url":"https://epaper.lokmat.com/main-editions/Goa%20Main/-1/1","logo":"assets/logos/lokmat-goa.svg"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()

def parse_date(text):
    patterns = [
        r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
        r"(\d{1,2},\s+[A-Za-z]{3,9}\s+\d{4})",
        r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            value = m.group(1)
            for fmt in ("%b %d, %Y", "%B %d, %Y", "%d, %B %Y", "%d, %b %Y", "%d %B %Y", "%d %b %Y"):
                try:
                    return datetime.strptime(value, fmt).strftime("%b %d, %Y")
                except ValueError:
                    pass
    return None

def make_id(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

def get_the_goan_latest(paper):
    r = requests.get(paper["url"], headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    published = None
    for text in soup.stripped_strings:
        m = re.search(r"Published\s+On\s*:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", text, re.I)
        if m:
            published = clean(m.group(1))
            break

    read_url = None
    for a in soup.find_all("a", href=True):
        if clean(a.get_text(" ", strip=True)).lower() == "read now":
            candidate = urljoin(paper["url"], a["href"])
            if "readwhere.com/read/" in candidate.lower():
                read_url = candidate
                break
            if read_url is None:
                read_url = candidate

    return {
        "id": make_id(paper["name"]),
        "name": paper["name"],
        "description": paper["description"],
        "language": paper["language"],
        "published": published or "Latest",
        "edition_url": paper["url"],
        "read_url": read_url or paper["url"],
        "logo": paper["logo"],
    }

def herald_candidate_is_valid(response, paper, date_text):
    if response.status_code != 200:
        return False
    final_url = response.url.rstrip("/")
    expected = f"/epaper/{paper['slug']}/{date_text}"
    if expected.lower() not in final_url.lower():
        return False

    text = clean(BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True))
    if "Page not found" in text or "404" in text[:500]:
        return False

    # Require both the expected date and the newspaper name so a redirect to
    # the generic Herald homepage cannot be mistaken for a valid issue.
    pretty = datetime.strptime(date_text, "%d-%m-%Y").strftime("%B %d, %Y")
    name_ok = ("O Heraldo" in text) if paper["slug"] == "oheraldo" else ("Dainik Herald" in text)
    return name_ok and (pretty in text or date_text in text)

def get_herald_latest(paper):
    base = f"https://epaper.heraldgoa.in/epaper/{paper['slug']}"
    today = datetime.now().astimezone()

    # The publisher's dated URL pattern is stable. Check today and previous
    # 14 days directly, newest first. This avoids relying on a cached homepage.
    for i in range(0, 15):
        dt = today - timedelta(days=i)
        date_text = dt.strftime("%d-%m-%Y")
        candidate = f"{base}/{date_text}"
        try:
            test = requests.get(
                candidate,
                headers=HEADERS,
                timeout=25,
                allow_redirects=True,
            )
            if herald_candidate_is_valid(test, paper, date_text):
                published = dt.strftime("%b %d, %Y")
                return {
                    "id": make_id(paper["name"]),
                    "name": paper["name"],
                    "description": paper["description"],
                    "language": paper["language"],
                    "published": published,
                    "edition_url": candidate,
                    "read_url": candidate,
                    "logo": paper["logo"],
                }
        except requests.RequestException as e:
            print(f"  check failed {candidate}: {e}")

    # Secondary discovery from the publisher homepage, useful if their URL
    # scheme changes in the future.
    homepage = "https://epaper.heraldgoa.in/"
    r = requests.get(homepage, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    pattern = re.compile(
        rf"/epaper/{re.escape(paper['slug'])}/(\d{{2}}-\d{{2}}-\d{{4}})(?:/|$)",
        re.I,
    )
    dates = []
    for a in soup.find_all("a", href=True):
        href = urljoin(homepage, a["href"])
        m = pattern.search(href)
        if m:
            try:
                dates.append((datetime.strptime(m.group(1), "%d-%m-%Y"), href, m.group(1)))
            except ValueError:
                pass
    for dt, href, date_text in sorted(dates, reverse=True):
        try:
            test = requests.get(href, headers=HEADERS, timeout=25, allow_redirects=True)
            if herald_candidate_is_valid(test, paper, date_text):
                return {
                    "id": make_id(paper["name"]),
                    "name": paper["name"],
                    "description": paper["description"],
                    "language": paper["language"],
                    "published": dt.strftime("%b %d, %Y"),
                    "edition_url": href,
                    "read_url": href,
                    "logo": paper["logo"],
                }
        except requests.RequestException:
            pass

    raise RuntimeError(f"Could not find a valid current {paper['name']} edition.")

def get_simple_latest(paper):
    r = requests.get(paper["url"], headers=HEADERS, timeout=30)
    r.raise_for_status()
    text = clean(BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True))
    published = parse_date(text) or "Latest"
    return {
        "id": make_id(paper["name"]),
        "name": paper["name"],
        "description": paper["description"],
        "language": paper["language"],
        "published": published,
        "edition_url": paper["url"],
        "read_url": paper["url"],
        "logo": paper["logo"],
    }

def load_old():
    path = Path("newspaper-data.json")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def fallback_for(paper, old_papers):
    old = old_papers.get(paper["name"])
    # Critical: if today's fetch fails, keep the last known-good URL.
    if old and old.get("read_url"):
        return old

    item = {
        "id": make_id(paper["name"]),
        "name": paper["name"],
        "description": paper["description"],
        "language": paper["language"],
        "published": "Unavailable",
        "edition_url": paper.get("url") or f"https://epaper.heraldgoa.in/epaper/{paper['slug']}/",
        "read_url": paper.get("url") or f"https://epaper.heraldgoa.in/epaper/{paper['slug']}/",
        "logo": paper["logo"],
    }
    return item

def main():
    old = load_old()
    old_papers = {p.get("name"): p for p in old.get("papers", [])}
    results = []

    for paper in THE_GOAN:
        try:
            results.append(get_the_goan_latest(paper))
            print(f"OK: {paper['name']}")
        except Exception as e:
            print(f"ERROR: {paper['name']}: {e}")
            results.append(fallback_for(paper, old_papers))

    for paper in HERALD:
        try:
            results.append(get_herald_latest(paper))
            print(f"OK: {paper['name']}")
        except Exception as e:
            print(f"ERROR: {paper['name']}: {e}")
            results.append(fallback_for(paper, old_papers))

    for paper in OTHER:
        try:
            results.append(get_simple_latest(paper))
            print(f"OK: {paper['name']}")
        except Exception as e:
            print(f"ERROR: {paper['name']}: {e}")
            results.append(fallback_for(paper, old_papers))

    output = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "papers": results,
    }
    Path("newspaper-data.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

if __name__ == "__main__":
    main()
