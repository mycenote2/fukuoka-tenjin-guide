#!/usr/bin/env python3
"""브라우저에서 뽑은 매장 후보(JSON) → Place ID + 상세정보 마크다운 표. 네트워크 불필요.

각 후보의 hex ftid 를 ChIJ Place ID 로 변환하고, 그 place_id 로 여는
'확인·공유 링크'(?api=1&query=...&query_place_id=...) 를 붙인다. 구글맵에 나와있는
주소(건물 포함)·층·카테고리·영업상태·평점도 있으면 같은 표에 담는다. 이 링크는 항상 그 가게
카드로 여는 안정적 permalink 라 공유링크 역할도 겸한다.

입력(JSON 배열). 각 항목 최소 {name, ftid}. 선택:
  addr, floor, category, hours, rating, reviews, phone, plusCode
  - extract_candidates.js 결과의 results 배열을 그대로 넣거나(전체 객체도 허용),
  - 사용자가 고른 항목만 추려 넣는다.

컬럼은 값이 하나라도 있는 것만 자동으로 나온다(빈 컬럼 생략).
기본: 매장/브랜드 · 주소 · 층 · 카테고리 · 영업 · 평점 · place_id · 확인·공유 링크.
--phone 붙이면 전화, --pluscode 붙이면 플러스코드 컬럼 추가.

사용법:
  echo '[{"name":"MUJI","ftid":"0x354191c7ec9f313d:0x589c0dfc213c97d8","addr":"JR博多シティ 6F","floor":"6F","category":"잡화점"}]' \
    | python3 build_table.py --title "후쿠오카"
  python3 build_table.py picked.json --title "후쿠오카 텐진" --pluscode
"""
import argparse
import json
import os
import re
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ftid_to_placeid import ftid_to_placeid  # noqa: E402

FTID_RE = re.compile(r"^0x[0-9a-f]+:0x[0-9a-f]+$")


def verify_url(name: str, pid: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote(name or '')}&query_place_id={pid}"


def esc(s) -> str:
    return str(s or "").replace("|", "\\|").replace("\n", " ").strip()


def rating_cell(it) -> str:
    r = esc(it.get("rating"))
    if not r:
        return ""
    rev = esc(it.get("reviews"))
    return f"{r} ({rev})" if rev else r


def main():
    ap = argparse.ArgumentParser(description="매장 후보 JSON → place_id + 상세정보 마크다운 표")
    ap.add_argument("infile", nargs="?", help="JSON 파일 경로 (생략 시 stdin)")
    ap.add_argument("--title", help="표 위에 붙일 지역/제목")
    ap.add_argument("--phone", action="store_true", help="전화 컬럼 추가")
    ap.add_argument("--pluscode", action="store_true", help="플러스코드 컬럼 추가")
    args = ap.parse_args()

    raw = open(args.infile, encoding="utf-8").read() if args.infile else sys.stdin.read()
    data = json.loads(raw)
    if isinstance(data, dict) and "results" in data:
        data = data["results"]
    if isinstance(data, dict):
        data = [data]

    # 컬럼 정의: (헤더, 값함수, 기본표시여부). 값이 하나도 없으면 자동 생략.
    detail_cols = [
        ("주소", lambda it: esc(it.get("addr")), True),
        ("층", lambda it: esc(it.get("floor")), True),
        ("카테고리", lambda it: esc(it.get("category")), True),
        ("영업", lambda it: esc(it.get("hours")), True),
        ("평점", rating_cell, True),
        ("전화", lambda it: esc(it.get("phone")), args.phone),
        ("플러스코드", lambda it: esc(it.get("plusCode")), args.pluscode),
    ]
    active = [(h, fn) for (h, fn, on) in detail_cols if on and any(fn(it) for it in data)]

    lines = []
    if args.title:
        lines.append(f"### {args.title} — Place ID\n")
    header = ["매장/브랜드"] + [h for h, _ in active] + ["place_id", "확인·공유 링크"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")

    for it in data:
        ftid = (it.get("ftid") or "").strip()
        if FTID_RE.match(ftid):
            pid = ftid_to_placeid(ftid)
            pid_cell = f"`{pid}`"
            link = f"[지도 열기]({verify_url(it.get('name'), pid)})"
        else:
            pid_cell, link = "⚠️ ftid 없음", "수동 확인 필요"
        row = [esc(it.get("name"))] + [fn(it) for _, fn in active] + [pid_cell, link]
        lines.append("| " + " | ".join(row) + " |")

    if any(h == "층" for h, _ in active):
        lines.append("\n> 주소·층은 **구글맵 표기 기준**이라 부정확할 수 있다. 가이드 반영 시 2개+ 소스로 교차검증할 것.")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
