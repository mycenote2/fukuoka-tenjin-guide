#!/usr/bin/env python3
"""구글맵 hex ftid(0x...:0x...) → Place ID(ChIJ...) 변환. 네트워크 불필요.

왜 필요한가:
  구글맵 공유 링크(maps.app.goo.gl)를 브라우저로 열면 /maps/place/ 페이지로 펼쳐지는데,
  이 페이지 HTML에는 ChIJ 형식 place_id가 **없고** hex ftid만 있다(URL의 `!1s0x...:0x...`).
  ChIJ는 그 hex를 protobuf로 감싸 base64url 인코딩한 값이라, 아래처럼 직접 변환하면 된다.

사용법:
  python3 ftid_to_placeid.py "0x354191857732230b:0xbc84bfe172ec6349"
  python3 ftid_to_placeid.py --selftest      # 알려진 쌍으로 알고리즘 검증

ftid 얻는 법 (브라우저에서):
  document.documentElement.innerHTML.match(/!1s(0x[0-9a-f]+:0x[0-9a-f]+)/)
  또는 location.href 의 `!1s0x...:0x...` 부분. (`!5s`는 다른 id이니 반드시 `!1s`를 쓸 것)

변환 후에는 반드시 검증한다:
  https://www.google.com/maps/search/?api=1&query=<이름>&query_place_id=<ChIJ...>
"""
import argparse
import base64
import struct
import sys


def ftid_to_placeid(ftid: str) -> str:
    """'0x<cell>:0x<fprint>' → 'ChIJ...'

    protobuf 구조: field1(length-delimited) { field1 fixed64 = cell, field2 fixed64 = fprint }
    바이트: 0x0A <len> 0x09 <cell LE 8B> 0x11 <fprint LE 8B>
    """
    a, b = ftid.strip().split(":")
    cell = int(a, 16)
    fprint = int(b, 16)
    inner = b"\x09" + struct.pack("<Q", cell) + b"\x11" + struct.pack("<Q", fprint)
    msg = b"\x0a" + bytes([len(inner)]) + inner
    return base64.urlsafe_b64encode(msg).decode().rstrip("=")


# 같은 구글맵 페이지에서 hex와 ChIJ를 동시에 확보해 검증한 쌍 (2026-07-16, 라시크 THREEPPY)
KNOWN_PAIRS = [
    ("0x354191ec52278c57:0xb545915ef34c7244", "ChIJV4wnUuyRQTURRHJM816RRbU"),
]


def selftest() -> bool:
    ok = True
    for ftid, expect in KNOWN_PAIRS:
        got = ftid_to_placeid(ftid)
        good = got == expect
        ok &= good
        print(f"{'✅' if good else '❌'} {ftid}\n   기대: {expect}\n   결과: {got}")
    return ok


def main():
    ap = argparse.ArgumentParser(description="구글맵 hex ftid → Place ID(ChIJ)")
    ap.add_argument("ftid", nargs="?", help='예: "0x354191857732230b:0xbc84bfe172ec6349"')
    ap.add_argument("--selftest", action="store_true", help="알려진 쌍으로 알고리즘 검증")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if not args.ftid:
        ap.error("ftid를 넣거나 --selftest 를 쓰세요")

    pid = ftid_to_placeid(args.ftid)
    print(f"ftid     : {args.ftid}")
    print(f"place_id : {pid}")
    print(f"검증 URL : https://www.google.com/maps/search/?api=1&query=&query_place_id={pid}")


if __name__ == "__main__":
    main()
