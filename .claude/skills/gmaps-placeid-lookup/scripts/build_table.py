#!/usr/bin/env python3
"""브라우저에서 뽑은 매장 후보(JSON) → Place ID 마크다운 표. 네트워크 불필요.

각 후보의 hex ftid 를 ChIJ Place ID 로 변환하고, 그 place_id 로 여는
'확인·공유 링크'(?api=1&query=...&query_place_id=...) 를 붙여 표로 만든다.
이 링크는 항상 그 가게 카드로 여는 안정적 permalink 라 공유링크 역할도 겸한다.

입력(JSON 배열). 각 항목 최소 {name, ftid}. 선택 {addr}:
  - extract_candidates.js 결과의 results 배열을 그대로 넣거나,
  - 사용자가 고른 항목만 추려 넣는다. (results 를 감싼 전체 객체도 허용)

사용법:
  echo '[{"name":"MUJI","ftid":"0x354191c7ec9f313d:0x589c0dfc213c97d8","addr":"JR博多시티 6F"}]' \
    | python3 build_table.py
  python3 build_table.py picked.json
  python3 build_table.py picked.json --title "후쿠오카 텐진"
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
    return f"https://www.google.com/maps/search/?api=1&query={quote(name)}&query_place_id={pid}"


def md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def main():
    ap = argparse.ArgumentParser(description="매장 후보 JSON → place_id 마크다운 표")
    ap.add_argument("infile", nargs="?", help="JSON 파일 경로 (생략 시 stdin)")
    ap.add_argument("--title", help="표 위에 붙일 지역/제목")
    args = ap.parse_args()

    raw = open(args.infile, encoding="utf-8").read() if args.infile else sys.stdin.read()
    data = json.loads(raw)
    if isinstance(data, dict) and "results" in data:
        data = data["results"]
    if isinstance(data, dict):
        data = [data]

    has_addr = any((it.get("addr") or it.get("text")) for it in data)
    lines = []
    if args.title:
        lines.append(f"### {args.title} — Place ID\n")
    header = ["매장/브랜드"] + (["주소·층"] if has_addr else []) + ["place_id", "확인·공유 링크"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")

    for it in data:
        name = md_escape(it.get("name", ""))
        ftid = (it.get("ftid") or "").strip()
        addr = md_escape(it.get("addr") or it.get("text") or "")
        if FTID_RE.match(ftid):
            pid = ftid_to_placeid(ftid)
            link = f"[지도 열기]({verify_url(it.get('name',''), pid)})"
            pid_cell = f"`{pid}`"
        else:
            pid_cell = "⚠️ ftid 없음"
            link = "수동 확인 필요"
        row = [name] + ([addr] if has_addr else []) + [pid_cell, link]
        lines.append("| " + " | ".join(row) + " |")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
