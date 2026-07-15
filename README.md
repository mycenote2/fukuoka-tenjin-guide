# 후쿠오카 텐진·다이묘 쇼핑 가이드 🛍️

텐진역에서 다이묘 거리까지, 걸어서 도는 후쿠오카 쇼핑 코스를 정리한 모바일 웹앱이에요.
가고 싶은 브랜드만 체크하면 최단 동선을 짜주고, 지도·내 위치·구글맵 연결까지 지원해요.

**🔗 라이브: https://fukuoka-tenjin-guide.vercel.app**

## 기능

- 🗺️ **지도** — 매장 18곳을 Leaflet + OpenStreetMap 지도에 표시
- ✅ **브랜드 체크리스트** — 88개 브랜드 중 가고 싶은 곳만 체크 (가나다순)
- ✨ **추천 동선 짜기** — 최근접 이웃 알고리즘으로 최단 도보 코스 계산
- 📍 **내 위치** — 현재 위치 기준으로 각 매장까지 거리 표시 (https 환경에서 동작)
- 🙋 **브랜드 요청 게시판** — 원하는 브랜드를 남기면 다음 업데이트 때 반영

## 구조

```
.
├── site/                 # 배포 대상 (Vercel rootDirectory)
│   ├── index.html        # 메인 가이드
│   ├── board.html        # 브랜드 요청 게시판
│   ├── privacy.html      # 개인정보처리방침
│   ├── ads.txt           # Google AdSense
│   ├── api/requests.js   # 게시판 API (Vercel 서버리스 함수 + Redis)
│   └── package.json
└── fukuoka_텐진_쇼핑가이드_v9.html   # 원본 보존본
```

## 기술 스택

- 순수 HTML + CSS + JS (프레임워크 없음)
- 지도: [Leaflet](https://leafletjs.com/) + OpenStreetMap
- 글꼴: [Pretendard](https://github.com/orioncactus/pretendard)
- 게시판 백엔드: Vercel 서버리스 함수 + Redis (ioredis)
- 배포: [Vercel](https://vercel.com/) (main 브랜치 push 시 자동 배포)

## 배포

`main` 브랜치에 push하면 Vercel이 자동으로 프로덕션에 배포해요.

---

원본 데이터는 체크인데이 카페 〈2026최신! 후쿠오카 쇼핑 가이드〉 글을 바탕으로,
주소·좌표는 직접 조사해서 정리했어요. 영업시간·입점 브랜드는 방문 전 한 번 더 확인하세요 ✌️
