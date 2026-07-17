#!/usr/bin/env python3
"""naver_crawl.py가 만든 JSONL에서 '브랜드 후보'를 뽑아 랭킹한다.

이건 브랜드를 확정하는 도구가 아니다. **후보를 좁혀서 사람(또는 클로드)이 판별할 수 있게**
만드는 도구다. 그래서 후보마다 실제 예문을 붙여 CSV로 내보낸다. 최종 판별은 그 예문을 보고 한다.

왜 형태소 분석기(Kiwi)를 쓰나 — 정규식으로는 안 되기 때문이다:
  정규식으로 한글 어절을 세면 상위권이 '있는/좋은/다른/있어서' 같은 용언 활용형으로 뒤덮인다.
  조사를 떼려고 하면 더 망가진다. '유니클로'의 끝 '로', '마루이'의 끝 '이'가 조사로 보이기 때문이다.
  외래어 브랜드는 로/이/도로 끝나는 게 흔해서 단순 조사 제거는 반드시 브랜드를 잘라먹는다.
  Kiwi는 이걸 형태소 단위로 정확히 갈라주고, 덤으로 고유명사(NNP)를 따로 태깅해준다.
  사전에 없는 브랜드(꼼데가르송·어반리서치·니코앤드·도큐핸즈)도 NNP로 잡아낸다 — 실측 확인함.

수집하는 태그:
  NNP = 고유명사 (돈키호테, 파르코, 빔즈)  -> kind=ko
  SL  = 외국어/영문  (BEAMS, PARCO, GU)    -> kind=en
  SW  = 기타기호인데 일본어 가타카나가 여기 온다 (ロフト) -> kind=ja
  + 붙어있는 NNP/SL/SN을 이어붙인 구 ('시부야 스크램블 스퀘어', '시부야109') -> kind=phrase

설치:
    pip3 install kiwipiepy

사용 예:
    python3 extract_brands.py research/naver/shibuya.jsonl --top 60 \
        --out research/naver/shibuya_brands.csv
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    from kiwipiepy import Kiwi
except ImportError:
    sys.exit("kiwipiepy가 없다. 설치: pip3 install kiwipiepy")

# 후보로 채택할 태그
TAG_KIND = {"NNP": "ko", "SL": "en", "SW": "ja"}

RE_JP = re.compile(r"[ぁ-んァ-ヴ一-龥]")            # SW 중 진짜 일본어만 통과시킨다
RE_URLISH = re.compile(r"(/|\.(com|net|org|co|kr|jp|gl|io|me|tv|ly)\b)", re.I)
RE_HAS_WORD = re.compile(r"[가-힣A-Za-zぁ-んァ-ヴ一-龥]{2}")
# 구에 허용할 문자. 〒, −(U+2212), % 같은 주소/기호 부스러기를 여기서 막는다.
RE_PHRASE_BAD = re.compile(r"[^\w\s가-힣ぁ-んァ-ヴ一-龥&'’.·\-]")
RE_PAIR = re.compile(r"([가-힣][가-힣0-9]{1,9})\s*\(\s*([A-Za-z][A-Za-z0-9 &'’.\-]{1,24})\s*\)")

DEFAULT_STOPWORDS = Path(__file__).resolve().parents[1] / "references" / "stopwords.txt"


def load_stopwords(paths) -> set:
    stop = set()
    for p in paths:
        p = Path(p)
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                stop.add(line.lower())
    return stop


def is_junk(form: str, kind: str, stop: set) -> bool:
    if len(form) < 2 or form.lower() in stop:
        return True
    if re.fullmatch(r"[\d\W_]+", form):        # 숫자·기호만
        return True
    if kind == "en":
        if RE_URLISH.search(form):             # blog.naver.com, maps.app.goo.gl
            return True
        if not re.search(r"[A-Za-z]{2}", form):
            return True
    if kind == "ja" and not RE_JP.search(form):
        return True
    return False


def phrase_ok(phrase: str, stop: set) -> bool:
    """구가 쓸 만한지. 구글맵 주소 블록에서 나오는 '1 Chome−12−18', '일본 〒' 류를 막는다."""
    if not (3 <= len(phrase) <= 40) or phrase.lower() in stop:
        return False
    if RE_PHRASE_BAD.search(phrase) or RE_URLISH.search(phrase):
        return False
    return bool(RE_HAS_WORD.search(phrase))


def iter_candidates(text: str, kiwi: Kiwi, stop: set):
    """문서 하나에서 (표기형, 종류) 후보를 만들어 낸다."""
    toks = kiwi.tokenize(text)

    usable = []          # 구를 이을 때 쓸 토큰만 추린다
    for t in toks:
        kind = TAG_KIND.get(t.tag)
        if not kind:
            continue
        if kind == "ja" and not RE_JP.search(t.form):
            continue     # SW인데 일본어가 아닌 것 = 〒, −, % 같은 기호. 구에 끼면 주소 쓰레기가 된다.
        if not is_junk(t.form, kind, stop):
            yield t.form, kind
        usable.append(t)

    # 붙어 있는 토큰들을 구로 이어붙인다 -> '시부야 스크램블 스퀘어'
    # (숫자 SN은 일부러 뺐다. 넣으면 주소 번지수가 구를 다 오염시킨다.)
    run = []
    for t in usable + [None]:
        if t is not None and (not run or t.start <= run[-1].start + run[-1].len + 1):
            run.append(t)
            continue
        for n in (2, 3):
            for i in range(len(run) - n + 1):
                chunk = run[i:i + n]
                # 전부 불용어(지명 나열 등)면 버린다. 하나라도 의미 있는 게 있어야 한다.
                if all(tk.form.lower() in stop for tk in chunk):
                    continue
                s, e = chunk[0].start, chunk[-1].start + chunk[-1].len
                phrase = re.sub(r"\s+", " ", text[s:e]).strip()
                if phrase_ok(phrase, stop):
                    yield phrase, "phrase"
        run = [t] if t is not None else []


def contexts_for(tok: str, docs: list, limit: int = 2):
    """후보가 실제 어떤 문맥에 나왔는지. 최종 판별은 이걸 보고 한다."""
    out = []
    for d in docs:
        idx = d["_text"].find(tok)
        if idx < 0:
            continue
        s, e = max(0, idx - 45), min(len(d["_text"]), idx + len(tok) + 45)
        out.append("…" + re.sub(r"\s+", " ", d["_text"][s:e]).strip() + "…")
        if len(out) >= limit:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description="크롤 JSONL -> 브랜드 후보 랭킹")
    ap.add_argument("jsonl", help="naver_crawl.py가 만든 JSONL")
    ap.add_argument("--top", type=int, default=60, help="상위 몇 개까지 (기본 60)")
    ap.add_argument("--min-df", type=int, default=3,
                    help="최소 문서빈도. 이보다 적은 글에 나온 후보는 버린다 (기본 3)")
    ap.add_argument("--out", "-o", help="CSV 출력 경로 (생략하면 화면에만)")
    ap.add_argument("--stopwords", action="append", default=[],
                    help="추가 불용어 파일. 기본 references/stopwords.txt 는 항상 함께 쓴다.")
    ap.add_argument("--max-chars", type=int, default=30000, help="글당 분석할 최대 글자수")
    args = ap.parse_args()

    docs = [json.loads(l) for l in open(args.jsonl, encoding="utf-8") if l.strip()]
    if not docs:
        sys.exit("빈 파일이다.")

    stop = load_stopwords([DEFAULT_STOPWORDS] + args.stopwords)
    kiwi = Kiwi()

    # 검색 키워드 자체는 후보에서 뺀다
    # ('시부야 쇼핑'으로 검색해놓고 1등이 '시부야'면 아무 정보가 없다)
    for q in {d.get("query", "") for d in docs}:
        for t in kiwi.tokenize(q):
            stop.add(t.form.lower())
        for w in q.split():
            stop.add(w.lower())

    df, tf, kind_of = Counter(), Counter(), {}
    pairs = defaultdict(Counter)
    for d in docs:
        d["_text"] = f"{d.get('title', '')}\n{d.get('body', '')}"[:args.max_chars]
        seen = set()
        for form, kind in iter_candidates(d["_text"], kiwi, stop):
            tf[form] += 1
            kind_of.setdefault(form, kind)
            if form not in seen:
                df[form] += 1
                seen.add(form)
        for m in RE_PAIR.finditer(d["_text"]):      # '빔즈(BEAMS)' = 브랜드라는 강한 신호
            pairs[m.group(1)][m.group(2).strip()] += 1

    rows = [{
        "candidate": form,
        "kind": kind_of[form],
        "df": n,
        "tf": tf[form],
        "pair": pairs[form].most_common(1)[0][0] if form in pairs else "",
    } for form, n in df.items() if n >= args.min_df]
    rows.sort(key=lambda r: (-r["df"], -r["tf"], r["candidate"]))
    rows = rows[:args.top]

    for r in rows:
        c = contexts_for(r["candidate"], docs)
        r["context1"] = c[0] if c else ""
        r["context2"] = c[1] if len(c) > 1 else ""

    print(f"\n문서 {len(docs)}개 / 후보 {len(df):,}개 중 상위 {len(rows)}개 (min-df={args.min_df})")
    print(f"{'#':>3}  {'후보':<26} {'종류':<7} {'DF':>4} {'TF':>5}  병기")
    print("-" * 80)
    for i, r in enumerate(rows, 1):
        pad = 26 - sum(2 if ord(ch) > 0x1100 else 1 for ch in r["candidate"])
        print(f"{i:>3}  {r['candidate']}{' ' * max(pad, 1)} {r['kind']:<7} "
              f"{r['df']:>4} {r['tf']:>5}  {r['pair']}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["candidate", "kind", "df", "tf", "pair",
                                              "context1", "context2"])
            w.writeheader()
            w.writerows(rows)
        print(f"\n[저장] {out}")
        print("→ context 열을 보고 '진짜 브랜드'만 골라내면 된다.")
        print("→ 지명·일반어가 계속 올라오면 references/stopwords.txt 에 추가해두면 다음부터 조용해진다.")


if __name__ == "__main__":
    main()
