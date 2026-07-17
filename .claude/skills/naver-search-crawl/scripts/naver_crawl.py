#!/usr/bin/env python3
"""네이버에서 블로그/카페글을 검색하고, 각 글의 본문까지 받아 JSONL로 저장한다.

두 가지 검색 모드:
  - scrape (기본, 키 불필요): search.naver.com을 페이지네이션하며 글 링크를 긁는다.
      실측상 8페이지 211건까지 중복 0·차단 없이 수집됐다. 제목·날짜·작성자는 목록엔 없지만
      어차피 페치하는 본문 페이지(og:title 등)에서 채우므로 API 모드 대비 잃는 정보가 없다.
  - api (--mode api, 키 필요): 네이버 검색 오픈 API. 안정적이고 news/web 소스도 되지만
      Client ID/Secret이 있어야 한다. 어차피 본문은 따로 페치하므로 API의 이점은 크지 않다.

왜 이런 구조인가 (실측으로 확인한 사실들):
  1. 두 모드 모두 본문은 안 준다(API는 200자 요약뿐). 브랜드 발굴엔 짧아서 본문을 따로 가져온다.
  2. blog.naver.com/{id}/{logNo} 를 그냥 GET하면 2.8KB짜리 iframe 껍데기만 온다(본문 0자).
     반드시 m.blog.naver.com/{id}/{logNo} 로 바꿔야 div.se-main-container 안에 본문이 들어있다.
     이게 네이버 블로그 크롤링에서 제일 흔하게 밟는 지뢰다.
  3. 카페글은 **공개 카페면** apis.naver.com 본문 API가 비로그인으로도 열린다.
     비공개/가입전용이면 실패하는데, 그땐 description(요약)으로 폴백한다.
  4. 검색결과 HTML의 클래스명은 난독화돼 자주 바뀐다. 그래서 scrape 모드는 셀렉터 대신
     안 바뀌는 URL 패턴으로 링크만 뽑는다.

사용 예:
    # 키 없이 (기본)
    python3 naver_crawl.py --query "일본 시부야 쇼핑" --query "시부야 쇼핑리스트" \
        --source blog,cafe --limit 100 --out research/naver/shibuya.jsonl
    # 오픈 API로 (news/web도 쓰고 싶을 때)
    python3 naver_crawl.py --mode api --query "시부야 쇼핑" --source blog,news \
        --limit 100 --out research/naver/shibuya.jsonl
"""
import argparse
import concurrent.futures as futures
import html
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlencode, urlparse

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

API_BASE = "https://openapi.naver.com/v1/search/{endpoint}.json"

# 사용자가 쓰는 이름 -> 네이버 API 엔드포인트
SOURCE_ALIASES = {
    "blog": "blog",
    "cafe": "cafearticle",
    "cafearticle": "cafearticle",
    "news": "news",
    "web": "webkr",
    "webkr": "webkr",
}

MAX_START = 1000   # 네이버 API 제한: start 최대 1000
MAX_DISPLAY = 100  # 네이버 API 제한: display 최대 100


# --------------------------------------------------------------------------
# 인증
# --------------------------------------------------------------------------
def load_env_file(path: Path) -> None:
    """.env.local 같은 파일의 KEY=VALUE를 os.environ에 (덮어쓰지 않고) 채운다."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v:
            os.environ.setdefault(k, v)


def get_credentials(repo_root: Path):
    for candidate in (repo_root / ".env.local", repo_root / ".env"):
        load_env_file(candidate)
    cid = os.environ.get("NAVER_CLIENT_ID")
    csec = os.environ.get("NAVER_CLIENT_SECRET")
    if not cid or not csec:
        sys.exit(
            "네이버 API 키가 없다.\n"
            "  1) https://developers.naver.com/apps/#/register 에서 앱 등록\n"
            "     - 사용 API: '검색' 선택 / 환경: 'WEB 설정' 아무 URL이나 (예: http://localhost)\n"
            "  2) 발급된 Client ID / Client Secret 을 repo 루트 .env.local 에 추가:\n"
            "       NAVER_CLIENT_ID=발급받은_아이디\n"
            "       NAVER_CLIENT_SECRET=발급받은_시크릿\n"
            "     (.gitignore 가 .env* 를 이미 막고 있어서 커밋되지 않는다)"
        )
    return {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}


# --------------------------------------------------------------------------
# 검색 (목록)
# --------------------------------------------------------------------------
def clean_html(s: str) -> str:
    """API가 돌려주는 <b>검색어</b> 강조 태그와 HTML 엔티티를 벗긴다."""
    s = re.sub(r"<[^>]+>", "", s or "")
    return html.unescape(s).strip()


def search(endpoint: str, query: str, limit: int, sort: str, headers: dict) -> list:
    """한 소스에서 limit개까지 검색 결과를 모은다. start/display 페이지네이션."""
    out, start = [], 1
    while len(out) < limit and start <= MAX_START:
        display = min(MAX_DISPLAY, limit - len(out))
        url = API_BASE.format(endpoint=endpoint) + "?" + urlencode(
            {"query": query, "display": display, "start": start, "sort": sort})
        r = requests.get(url, headers=headers, timeout=20)

        if r.status_code == 401:
            sys.exit("네이버 API 401: Client ID/Secret이 틀렸다. .env.local 확인.")
        if r.status_code == 429:
            print("  ! 429 rate limit — 5초 쉬고 재시도", file=sys.stderr)
            time.sleep(5)
            continue
        if r.status_code != 200:
            print(f"  ! {endpoint} start={start} HTTP {r.status_code}: {r.text[:200]}",
                  file=sys.stderr)
            break

        items = r.json().get("items", [])
        if not items:
            break
        out.extend(items)
        start += display
        time.sleep(0.15)  # 예의상 간격
    return out[:limit]


def normalize_item(item: dict, source: str, query: str) -> dict:
    return {
        "source": source,
        "query": query,
        "title": clean_html(item.get("title", "")),
        "link": item.get("link", ""),
        "description": clean_html(item.get("description", "")),
        "postdate": item.get("postdate", ""),
        "author": item.get("bloggername") or item.get("cafename") or "",
        "body": "",
        "body_status": "not_fetched",
    }


# --------------------------------------------------------------------------
# 검색 (스크래핑) — API 키 없이 search.naver.com에서 링크만 긁는다.
# --------------------------------------------------------------------------
# 왜 링크만 긁나: 네이버 검색결과 HTML의 클래스명은 난독화돼 자주 바뀌어서 제목/날짜를
# 셀렉터로 파싱하면 잘 깨진다. 하지만 URL 패턴(blog.naver.com/{id}/{logNo})은 안 바뀐다.
# 그래서 목록에선 링크만 뽑고, 제목·날짜·작성자는 어차피 페치하는 본문 페이지에서 채운다.
SCRAPE_TABS = {
    "blog": ("tab.blog.all", r"https?://blog\.naver\.com/[A-Za-z0-9_-]+/\d+"),
    "cafe": ("tab.cafe.all", r"https?://cafe\.naver\.com/[A-Za-z0-9_-]+/\d+"),
}


def scrape_search(source: str, query: str, limit: int, sort: str,
                  sess: requests.Session) -> list:
    """search.naver.com 블로그/카페 탭을 페이지네이션하며 글 링크를 모은다 (키 불필요)."""
    ssc, pat = SCRAPE_TABS[source]
    rx = re.compile(pat)
    nso = "&nso=so:dd,p:all" if sort == "date" else ""
    links, seen, start, stall = [], set(), 1, 0
    while len(links) < limit and start <= 1000:
        url = (f"https://search.naver.com/search.naver?ssc={ssc}"
               f"&query={quote(query)}&start={start}{nso}")
        try:
            r = sess.get(url, headers={"Referer": "https://search.naver.com/"}, timeout=20)
        except requests.RequestException as e:
            print(f"  ! scrape {source} start={start}: {type(e).__name__}", file=sys.stderr)
            break
        if r.status_code != 200:
            print(f"  ! scrape {source} start={start} HTTP {r.status_code}", file=sys.stderr)
            break
        # 한 페이지 HTML 안에 같은 글 URL이 썸네일·제목·작성자 링크로 여러 번 나온다.
        # seen을 즉시 갱신하며 걸러야 페이지 내 중복까지 제거된다.
        fresh = 0
        for m in rx.finditer(r.text):
            l = m.group(0)
            if l not in seen:
                seen.add(l)
                links.append(l)
                fresh += 1
        if not fresh:                      # 새 링크가 안 나오면 결과 소진으로 보고 종료
            stall += 1
            if stall >= 2:
                break
        else:
            stall = 0
        start += 30
        time.sleep(0.4)                    # 예의상 간격 (실측상 차단 없었지만 넉넉히)
    return [{"source": source, "query": query, "title": "", "link": l,
             "description": "", "postdate": "", "author": "",
             "body": "", "body_status": "not_fetched"} for l in links[:limit]]


# --------------------------------------------------------------------------
# 본문 추출
# --------------------------------------------------------------------------
_cafe_clubid_cache = {}


def _text(node) -> str:
    return re.sub(r"[ \t​\xa0]+", " ",
                  re.sub(r"\n{3,}", "\n\n", node.get_text("\n", strip=True)))


def _meta_from_soup(soup) -> dict:
    """og:title·작성일·닉네임을 페이지에서 뽑는다. 스크래핑 모드는 목록에 제목이 없어서 여기서 채운다."""
    def og(prop):
        t = soup.select_one(f'meta[property="{prop}"]')
        return t["content"].strip() if t and t.get("content") else ""
    date_el = (soup.select_one("span.se_publishDate") or soup.select_one("p.blog_date")
               or soup.select_one("span.date"))
    return {
        "title": og("og:title"),
        "author": og("naverblog:nickname"),
        "postdate": date_el.get_text(strip=True) if date_el else "",
    }


def fetch_naver_blog(link: str, sess: requests.Session) -> tuple:
    """blog.naver.com -> m.blog.naver.com 으로 바꿔서 본문 추출. (본문, 상태, 메타) 반환."""
    m = re.search(r"blog\.naver\.com/([^/?#]+)/(\d+)", link)
    if not m:
        m2 = re.search(r"blogId=([^&]+).*?logNo=(\d+)", link)
        if not m2:
            return "", "blog_url_unparsed", {}
        blog_id, log_no = m2.group(1), m2.group(2)
    else:
        blog_id, log_no = m.group(1), m.group(2)

    url = f"https://m.blog.naver.com/{blog_id}/{log_no}"
    r = sess.get(url, timeout=20)
    if r.status_code != 200:
        return "", f"http_{r.status_code}", {}

    soup = BeautifulSoup(r.text, "lxml")
    meta = _meta_from_soup(soup)
    body = (soup.select_one("div.se-main-container")      # 스마트에디터 ONE (현재 표준)
            or soup.select_one("div#postViewArea")        # 구 에디터
            or soup.select_one("div.post_ct")             # 더 옛날
            or soup.select_one("div#viewTypeSelector"))
    if body is None:
        return "", "no_body_selector", meta
    return _text(body), "ok", meta


def resolve_cafe_clubid(cafe_name: str, sess: requests.Session):
    """카페 주소명(joonggonara) -> 숫자 clubId. 본문 API가 숫자 id를 요구해서 필요."""
    if cafe_name in _cafe_clubid_cache:
        return _cafe_clubid_cache[cafe_name]
    try:
        r = sess.get(f"https://cafe.naver.com/{cafe_name}", timeout=20)
        m = re.search(r"clubid=(\d+)", r.text, re.I) or \
            re.search(r"cafeId[\"']?\s*[:=]\s*[\"']?(\d+)", r.text, re.I)
        clubid = m.group(1) if m else None
    except requests.RequestException:
        clubid = None
    _cafe_clubid_cache[cafe_name] = clubid
    return clubid


def fetch_naver_cafe(link: str, sess: requests.Session) -> tuple:
    """공개 카페면 비로그인으로도 본문 API가 열린다. 비공개면 실패 -> description 폴백."""
    m = re.search(r"cafe\.naver\.com/([^/?#]+)/(\d+)", link)
    if m:
        clubid = resolve_cafe_clubid(m.group(1), sess)
        articleid = m.group(2)
    else:
        m2 = re.search(r"clubid=(\d+).*?articleid=(\d+)", link, re.I)
        if not m2:
            return "", "cafe_url_unparsed", {}
        clubid, articleid = m2.group(1), m2.group(2)
    if not clubid:
        return "", "cafe_clubid_unresolved", {}

    url = (f"https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{clubid}"
           f"/articles/{articleid}?query=&useCafeId=true&requestFrom=A")
    r = sess.get(url, headers={"Referer": "https://cafe.naver.com/"}, timeout=20)
    if r.status_code != 200:
        return "", f"http_{r.status_code}", {}
    try:
        art = r.json()["result"]["article"]
    except (ValueError, KeyError):
        return "", "cafe_json_unexpected", {}

    wd = art.get("writeDate")            # epoch 밀리초로 온다 -> 사람이 읽는 날짜로
    try:
        postdate = (time.strftime("%Y. %-m. %-d.", time.localtime(int(wd) / 1000))
                    if wd else "")
    except (ValueError, TypeError, OSError):
        postdate = str(wd or "")
    meta = {"title": (art.get("subject") or "").strip(),
            "author": (art.get("writer") or {}).get("nick", ""),
            "postdate": postdate}
    content = art.get("contentHtml") or ""
    if not content:
        return "", "cafe_no_content", meta
    text = _text(BeautifulSoup(content, "lxml"))
    # 카페 본문에 박히는 이미지/첨부 자리표시자 제거
    text = re.sub(r"\[\[\[CONTENT-ELEMENT-\d+\]\]\]", " ", text)
    return text.strip(), "ok", meta


def fetch_generic(link: str, sess: requests.Session) -> tuple:
    """티스토리·브런치 등 그 외 사이트. 스크립트/네비 걷어내고 본문 후보를 잡는다."""
    r = sess.get(link, timeout=20)
    if r.status_code != 200:
        return "", f"http_{r.status_code}", {}
    soup = BeautifulSoup(r.text, "lxml")
    og = soup.select_one('meta[property="og:title"]')
    meta = {"title": og["content"].strip() if og and og.get("content") else ""}
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
        tag.decompose()
    body = (soup.select_one("article")
            or soup.select_one("div.entry-content")   # 티스토리 계열
            or soup.select_one("div.tt_article_useless_p_margin")
            or soup.select_one("div.wrap_body")       # 브런치
            or soup.select_one("main")
            or soup.body)
    if body is None:
        return "", "no_body_selector", meta
    return _text(body), "ok", meta


def fetch_body(rec: dict, sess: requests.Session, delay: float) -> dict:
    """레코드 하나의 본문을 채운다. 어떤 실패든 body_status에 이유를 남기고 죽지 않는다."""
    time.sleep(delay * (0.5 + random.random()))  # 동시요청이 몰리지 않게 살짝 흔든다
    link = rec["link"]
    host = urlparse(link).netloc
    try:
        if "blog.naver.com" in host:
            body, status, meta = fetch_naver_blog(link, sess)
        elif "cafe.naver.com" in host:
            body, status, meta = fetch_naver_cafe(link, sess)
        else:
            body, status, meta = fetch_generic(link, sess)
    except requests.RequestException as e:
        body, status, meta = "", f"error_{type(e).__name__}", {}

    # 목록에서 비워둔 필드(스크래핑 모드)를 본문 페이지에서 얻은 값으로 채운다. API 모드는 이미 차 있음.
    for k in ("title", "author", "postdate"):
        if not rec.get(k) and meta.get(k):
            rec[k] = meta[k]

    if status != "ok" or len(body) < 50:
        # 본문을 못 받으면 최소한 API 요약이라도 남긴다 (브랜드 신호가 아예 0이 되진 않게)
        rec["body"] = rec["description"]
        rec["body_status"] = status if status != "ok" else "too_short_used_description"
    else:
        rec["body"] = body
        rec["body_status"] = "ok"
    return rec


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="네이버 검색 API로 블로그/카페글 수집 + 본문 추출 -> JSONL")
    ap.add_argument("--query", "-q", action="append", required=True,
                    help="검색 키워드. 여러 번 쓰면 여러 키워드를 합쳐서 수집한다.")
    ap.add_argument("--mode", default="scrape", choices=["scrape", "api"],
                    help="scrape=키 없이 검색페이지 크롤(기본) / api=네이버 검색 오픈 API")
    ap.add_argument("--source", default="blog,cafe",
                    help="scrape 모드: blog,cafe / api 모드: blog,cafe,news,web (기본: blog,cafe)")
    ap.add_argument("--limit", type=int, default=100,
                    help="키워드×소스당 최대 건수 (기본 100)")
    ap.add_argument("--sort", default="sim", choices=["sim", "date"],
                    help="sim=정확도순(기본), date=최신순")
    ap.add_argument("--out", "-o", required=True, help="출력 JSONL 경로")
    ap.add_argument("--no-bodies", action="store_true", help="본문 없이 목록만 수집")
    ap.add_argument("--workers", type=int, default=4, help="본문 동시 요청 수 (기본 4)")
    ap.add_argument("--delay", type=float, default=0.3, help="본문 요청 간 간격 초 (기본 0.3)")
    args = ap.parse_args()

    sess = requests.Session()
    sess.headers.update({"User-Agent": UA})

    # --- 소스 파싱 (모드에 따라 허용 목록이 다르다) ---
    src_names = [s.strip().lower() for s in args.source.split(",") if s.strip()]
    if args.mode == "api":
        repo_root = Path(__file__).resolve().parents[4]
        headers = get_credentials(repo_root)
        sources = []
        for s in src_names:
            if s not in SOURCE_ALIASES:
                sys.exit(f"모르는 소스: {s} (api 가능: {', '.join(sorted(set(SOURCE_ALIASES)))})")
            sources.append(s)
    else:
        for s in src_names:
            if s not in SCRAPE_TABS:
                sys.exit(f"scrape 모드는 {', '.join(SCRAPE_TABS)} 만 된다 (news/web은 --mode api). 받은 값: {s}")
        sources = src_names

    # 1) 목록 수집 + 링크 기준 중복 제거
    records, seen = [], set()
    for query in args.query:
        for name in sources:
            if args.mode == "api":
                raw = search(SOURCE_ALIASES[name], query, args.limit, args.sort, headers)
                items = [normalize_item(it, name, query) for it in raw]
            else:
                items = scrape_search(name, query, args.limit, args.sort, sess)
            new = 0
            for rec in items:
                link = rec.get("link", "")
                if not link or link in seen:
                    continue
                seen.add(link)
                records.append(rec)
                new += 1
            print(f"[검색:{args.mode}] {query!r} / {name}: {len(items)}건 수신, 신규 {new}건")

    print(f"[검색] 중복 제거 후 총 {len(records)}건")
    if not records:
        sys.exit("수집된 글이 없다. 키워드를 바꿔보자.")

    # 2) 본문 수집
    if not args.no_bodies:
        done = 0
        with futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(fetch_body, r, sess, args.delay) for r in records]
            for _ in futures.as_completed(futs):
                done += 1
                if done % 20 == 0 or done == len(records):
                    print(f"[본문] {done}/{len(records)}")

        ok = sum(1 for r in records if r["body_status"] == "ok")
        print(f"[본문] 성공 {ok}/{len(records)} ({ok * 100 // max(len(records), 1)}%)")
        fails = {}
        for r in records:
            if r["body_status"] != "ok":
                fails[r["body_status"]] = fails.get(r["body_status"], 0) + 1
        if fails:
            print("[본문] 실패 사유:", ", ".join(f"{k}={v}" for k, v in
                                              sorted(fails.items(), key=lambda x: -x[1])))

    # 3) 저장
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    chars = sum(len(r["body"]) for r in records)
    print(f"[저장] {out}  ({len(records)}건, 본문 {chars:,}자)")


if __name__ == "__main__":
    main()
