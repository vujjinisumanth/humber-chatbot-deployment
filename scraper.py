import os
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm
from urllib.parse import urljoin, urlparse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

FULLTIME_URL = "https://humber.ca/explore-programs/search/full-time-programs"
CPL_URL = "https://humber.ca/explore-programs/search/professional-learning"

OUTPUT_DIR = "output"
OUTPUT_FULLTIME = os.path.join(OUTPUT_DIR, "Humber_FullTime2.xlsx")
OUTPUT_CPL = os.path.join(OUTPUT_DIR, "Humber_CPL2.xlsx")


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def clean_text(s):
    s = "" if s is None else str(s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_heading(s):
    return clean_text(s).lower()


def get_soup(url, session=None):
    s = session or requests.Session()
    r = s.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml"), r.text


def section_text_fuzzy(soup, keywords):
    keywords = [k.lower() for k in keywords]
    main = soup.find("main") or soup
    headings = main.find_all(["h2", "h3", "h4"])

    target = None
    for h in headings:
        ht = normalize_heading(h.get_text(" ", strip=True))
        if any(k in ht for k in keywords):
            target = h
            break

    if not target:
        return ""

    parts = []
    for sib in target.find_all_next():
        if sib.name in ["h2", "h3", "h4"] and sib is not target:
            break
        if sib.name in ["p", "li"]:
            t = clean_text(sib.get_text(" ", strip=True))
            if t:
                parts.append(t)

    return "\n".join(parts).strip()


def best_faculty_from_url(url):
    low = url.lower()
    if "continuous-professional-learning" in low:
        return "Continuous Professional Learning"
    if "business" in low:
        return "Longo Faculty of Business"
    if "media" in low or "creative" in low:
        return "Faculty of Media, Creative Arts, and Design"
    if "health" in low or "nursing" in low:
        return "Faculty of Health & Life Sciences"
    if "liberal" in low:
        return "Faculty of Liberal Arts & Sciences"
    if "community" in low or "social" in low:
        return "Faculty of Social & Community Services"
    if "technology" in low or "engineering" in low:
        return "Faculty of Applied Sciences & Technology"
    return ""


def extract_faculty_from_page(soup):
    faculty_keywords = {
        "applied sciences": "Faculty of Applied Sciences & Technology",
        "applied technology": "Faculty of Applied Sciences & Technology",
        "clean energy": "Faculty of Applied Sciences & Technology",
        "longo faculty of business": "Longo Faculty of Business",
        "faculty of business": "Longo Faculty of Business",
        "health & life sciences": "Faculty of Health & Life Sciences",
        "health sciences": "Faculty of Health & Life Sciences",
        "nursing": "Faculty of Health & Life Sciences",
        "liberal arts": "Faculty of Liberal Arts & Sciences",
        "media, creative arts": "Faculty of Media, Creative Arts, and Design",
        "media arts": "Faculty of Media, Creative Arts, and Design",
        "social & community": "Faculty of Social & Community Services",
        "community services": "Faculty of Social & Community Services",
    }
    main = soup.find("main") or soup
    for a in main.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True)).lower()
        for keyword, faculty_name in faculty_keywords.items():
            if keyword in text:
                return faculty_name
    return ""


def extract_program_code_and_credential(page_text):
    code = ""
    cred = ""

    m = re.search(r"Program Code:\s*([A-Z0-9-]+)", page_text, flags=re.I)
    if m:
        code = m.group(1).strip()

    m = re.search(r"Credential:\s*(.+)", page_text, flags=re.I)
    if m:
        cred = clean_text(m.group(1))

    return code, cred


def _norm_label(s):
    s = clean_text(s).lower()
    s = re.sub(r"[:\s]+$", "", s)
    return s


def extract_labeled_value(soup, label_aliases):
    aliases = {_norm_label(a) for a in label_aliases if a}
    main = soup.find("main") or soup

    full_text = main.get_text(separator="|", strip=True)
    parts = [p.strip() for p in full_text.split("|") if p.strip()]
    for i, part in enumerate(parts):
        if _norm_label(part) in aliases and i + 1 < len(parts):
            val = parts[i + 1]
            if val and len(val) < 300:
                return clean_text(val)

    for dt in main.find_all("dt"):
        lab = _norm_label(dt.get_text(" ", strip=True))
        if lab in aliases:
            dd = dt.find_next_sibling("dd")
            if dd:
                return clean_text(dd.get_text(" ", strip=True))

    for tr in main.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) >= 2:
            lab = _norm_label(cells[0].get_text(" ", strip=True))
            if lab in aliases:
                return clean_text(cells[1].get_text(" ", strip=True))

    for strong in main.find_all(["strong", "b"]):
        lab = _norm_label(strong.get_text(" ", strip=True))
        if lab in aliases:
            parent_text = clean_text(strong.parent.get_text(" ", strip=True))
            label_text = clean_text(strong.get_text(" ", strip=True)).rstrip(":")
            val = re.sub(rf"^{re.escape(label_text)}\s*:?\s*", "", parent_text, flags=re.I)
            return clean_text(val)

    return ""


def regex_scan_value(rendered_text, patterns):
    txt = rendered_text or ""
    for pat in patterns:
        m = re.search(pat, txt, flags=re.I)
        if m:
            return clean_text(m.group(1))
    return ""


def scrape_fulltime_detail(url, session):
    try:
        soup, html = get_soup(url, session)
    except Exception as e:
        return {"SOURCE URL": url, "PROGRAM NAME": "", "ERROR": str(e)}

    main = soup.find("main") or soup
    h1 = main.find("h1") or soup.find("h1")
    program_name = clean_text(h1.get_text(" ", strip=True)) if h1 else ""

    main_text = main.get_text("\n", strip=True)

    code = extract_labeled_value(soup, ["Program Code", "Code"])
    credentials = extract_labeled_value(soup, ["Credential", "Credentials"])
    pgwp = extract_labeled_value(soup, ["PGWP-Eligible", "PGWP Eligible", "PGWP eligibility", "PGWP"])
    start_dates = extract_labeled_value(soup, ["Start Dates", "Start Date", "Intakes", "Intake"])
    length = extract_labeled_value(soup, ["Program Length", "Duration", "Length"])

    if not code or not credentials:
        code2, cred2 = extract_program_code_and_credential(main_text)
        if not code:
            code = code2
        if not credentials:
            credentials = cred2

    if not pgwp:
        pgwp = regex_scan_value(main_text, [
            r"PGWP[-\s]*Eligible\s*[:|]\s*([^\n|]+)",
            r"PGWP\s*Eligibility\s*[:|]\s*([^\n|]+)"
        ])

    if not start_dates:
        start_dates = regex_scan_value(main_text, [
            r"Start\s*Dates?\s*[:|]\s*([^\n|]+)",
            r"Intakes?\s*[:|]\s*([^\n|]+)"
        ])

    if not length:
        length = regex_scan_value(main_text, [
            r"Program\s*Length\s*[:|]\s*([^\n|]+)",
            r"Duration\s*[:|]\s*([^\n|]+)"
        ])

    overview = section_text_fuzzy(soup, ["program overview", "overview", "about the program", "about"])
    your_career = section_text_fuzzy(soup, ["your career", "careers", "career"])
    wil = section_text_fuzzy(soup, ["work-integrated learning", "work integrated learning", "co-op", "coop", "placement"])
    wil_flag = "Yes" if wil else ""
    faculty = extract_faculty_from_page(soup) or best_faculty_from_url(url)

    return {
        "PROGRAM NAME": program_name,
        "PROGRAM OVERVIEW": overview,
        "CREDENTIALS": clean_text(credentials),
        "CODE": clean_text(code),
        "WORK INTEGRATED LEARNING": wil_flag,
        "FACULTY": faculty,
        "YOUR CAREER": your_career,
        "PGWP-Eligible": clean_text(pgwp),
        "Start Dates": clean_text(start_dates),
        "Program Length": clean_text(length),
        "SOURCE URL": url,
    }


def scrape_cpl_detail(url, session):
    try:
        soup, html = get_soup(url, session)
    except Exception as e:
        return {"SOURCE URL": url, "PROGRAM NAME": "", "ERROR": str(e)}

    main = soup.find("main") or soup
    h1 = main.find("h1") or soup.find("h1")
    program_name = clean_text(h1.get_text(" ", strip=True)) if h1 else ""
    page_text = main.get_text("\n", strip=True)

    code, credentials = extract_program_code_and_credential(page_text)
    if not code:
        code = extract_labeled_value(soup, ["Program Code", "Code"])
    if not credentials:
        credentials = extract_labeled_value(soup, ["Credential", "Credentials"])

    overview = section_text_fuzzy(soup, ["program overview", "overview", "about", "description"])
    your_career = section_text_fuzzy(soup, ["your career", "careers", "career", "who should attend"])
    wil = section_text_fuzzy(soup, ["work-integrated learning", "work integrated learning", "co-op", "coop", "placement"])
    wil_flag = "Yes" if wil else ""

    return {
        "PROGRAM NAME": program_name,
        "PROGRAM OVERVIEW": overview,
        "CREDENTIALS": clean_text(credentials),
        "CODE": clean_text(code),
        "WORK INTEGRATED LEARNING": wil_flag,
        "FACULTY": extract_faculty_from_page(soup) or best_faculty_from_url(url),
        "YOUR CAREER": your_career,
        "PGWP-Eligible": "",
        "Start Dates": "",
        "Program Length": "",
        "SOURCE URL": url,
    }


def collect_fulltime_program_links():
    links = set()
    session = requests.Session()
    session.headers.update(HEADERS)

    page_num = 0
    empty_streak = 0

    while True:
        url = FULLTIME_URL if page_num == 0 else f"{FULLTIME_URL}?page={page_num}"
        try:
            soup, html = get_soup(url, session)
        except Exception as e:
            print(f"Warning: failed to fetch full-time page {page_num}: {e}")
            break

        new_links = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/explore-programs/programs/" not in href:
                continue
            abs_url = urljoin(FULLTIME_URL, href).split("#")[0].rstrip("/")
            path = urlparse(abs_url).path
            segments = [s for s in path.split("/") if s]
            if len(segments) >= 3 and segments[-2] == "programs":
                new_links.add(abs_url)

        added = new_links - links
        links.update(new_links)
        print(f"Full-Time page {page_num}: found {len(new_links)} links (+{len(added)} new)")

        if not added:
            empty_streak += 1
            if empty_streak >= 3:
                break
        else:
            empty_streak = 0

        page_num += 1
        time.sleep(0.5)

    links = sorted(links)
    print("Collected Full-Time links:", len(links))
    print("Sample:", links[:5])
    return links


def collect_cpl_program_links():
    links = set()
    session = requests.Session()
    session.headers.update(HEADERS)

    page_num = 0
    empty_streak = 0

    while True:
        url = CPL_URL if page_num == 0 else f"{CPL_URL}?page={page_num}"
        try:
            soup, html = get_soup(url, session)
        except Exception as e:
            print(f"Warning: failed to fetch CPL page {page_num}: {e}")
            break

        new_links = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/explore-programs/certificates/" not in href:
                continue
            abs_url = urljoin(CPL_URL, href).split("#")[0].rstrip("/")
            path = urlparse(abs_url).path
            segments = [s for s in path.split("/") if s]
            if len(segments) >= 3 and segments[-2] == "certificates":
                new_links.add(abs_url)

        added = new_links - links
        links.update(new_links)
        print(f"CPL page {page_num}: found {len(new_links)} links (+{len(added)} new)")

        if not added:
            empty_streak += 1
            if empty_streak >= 3:
                break
        else:
            empty_streak = 0

        page_num += 1
        time.sleep(0.5)

    links = sorted(links)
    print("Collected CPL links:", len(links))
    print("Sample:", links[:5])
    return links


def save_excel(rows, out_xlsx):
    df = pd.DataFrame(rows).fillna("")

    col_order = [
        "PROGRAM NAME",
        "PROGRAM OVERVIEW",
        "CREDENTIALS",
        "CODE",
        "WORK INTEGRATED LEARNING",
        "FACULTY",
        "YOUR CAREER",
        "PGWP-Eligible",
        "Start Dates",
        "Program Length",
        "SOURCE URL",
    ]

    for c in col_order:
        if c not in df.columns:
            df[c] = ""

    extra = [c for c in df.columns if c not in col_order]
    df = df[col_order + extra]
    df.to_excel(out_xlsx, index=False)
    print("Saved:", out_xlsx)


def run_fulltime():
    session = requests.Session()
    session.headers.update(HEADERS)
    urls = collect_fulltime_program_links()
    rows = []

    for u in tqdm(urls, desc="Scraping FULL-TIME"):
        try:
            rows.append(scrape_fulltime_detail(u, session))
            time.sleep(0.3)
        except Exception as e:
            rows.append({"SOURCE URL": u, "PROGRAM NAME": "", "ERROR": str(e)})

    save_excel(rows, OUTPUT_FULLTIME)


def run_cpl():
    session = requests.Session()
    session.headers.update(HEADERS)
    urls = collect_cpl_program_links()
    rows = []

    for u in tqdm(urls, desc="Scraping CPL"):
        try:
            rows.append(scrape_cpl_detail(u, session))
            time.sleep(0.3)
        except Exception as e:
            rows.append({"SOURCE URL": u, "PROGRAM NAME": "", "ERROR": str(e)})

    save_excel(rows, OUTPUT_CPL)


if __name__ == "__main__":
    ensure_output_dir()
    run_fulltime()
    run_cpl()