#!/usr/bin/env python3
"""구글맵 플러스코드(Open Location Code) → 위도/경도 변환. 네트워크 불필요.

사용법:
  python3 decode_pluscode.py "HCQ2+85" --ref-lat 33.5902 --ref-lng 130.4017
  python3 decode_pluscode.py "8Q5GHCQ2+85"          # 전체 코드는 기준점 불필요

짧은 코드(앞자리 생략형, 예 "HCQ2+85")는 기준 위치로 앞자리를 복원한다.
--ref-* 기본값은 후쿠오카 텐진 근방이라, 후쿠오카 코드면 그냥 코드만 넘겨도 된다.
"""
import argparse

A = "23456789CFGHJMPQRVWX"  # Open Location Code 문자셋 (base 20)


def encode(lat, lng, length=10):
    lat += 90
    lng += 180
    latp = lngp = 20.0
    code = ""
    for _ in range(length // 2):
        code += A[int(lat // latp)]; lat %= latp; latp /= 20
        code += A[int(lng // lngp)]; lng %= lngp; lngp /= 20
    return code


def recover(short, rlat, rlng):
    """짧은 코드 앞에 기준 위치의 앞 4자리를 붙여 전체 코드로 복원."""
    s = short.replace("+", "").upper()
    ref = encode(rlat, rlng, 10)  # '+' 없는 10자리
    full = ref[:4] + s
    return full[:8] + "+" + full[8:]


def decode(code):
    """전체 코드(또는 '+' 포함 코드) → (중심 위도, 중심 경도)."""
    c = code.replace("+", "").upper()
    lat, lng = -90.0, -180.0
    latp = lngp = 20.0
    for i in range(0, len(c), 2):
        lat += A.index(c[i]) * latp; latp /= 20
        lng += A.index(c[i + 1]) * lngp; lngp /= 20
    # 코너 + 반 셀 = 셀 중심
    return lat + latp * 20 / 2, lng + lngp * 20 / 2


def main():
    ap = argparse.ArgumentParser(description="플러스코드 → 위도/경도")
    ap.add_argument("code", help='플러스코드 (예: "HCQ2+85" 또는 "8Q5GHCQ2+85")')
    ap.add_argument("--ref-lat", type=float, default=33.5902, help="짧은 코드 복원 기준 위도 (기본: 후쿠오카 텐진)")
    ap.add_argument("--ref-lng", type=float, default=130.4017, help="짧은 코드 복원 기준 경도 (기본: 후쿠오카 텐진)")
    args = ap.parse_args()

    code = args.code.strip()
    before_plus = code.split("+")[0]
    # 전체 코드는 '+' 앞이 8자리. 그보다 짧으면 복원 필요.
    if len(before_plus) < 8:
        full = recover(code, args.ref_lat, args.ref_lng)
    else:
        full = code if "+" in code else code[:8] + "+" + code[8:]

    lat, lng = decode(full)
    print(f"입력 코드   : {code}")
    print(f"전체 코드   : {full}")
    print(f"좌표        : {lat:.6f}, {lng:.6f}")
    print(f"구글맵 확인 : https://www.google.com/maps?q={lat:.6f},{lng:.6f}")


if __name__ == "__main__":
    main()
