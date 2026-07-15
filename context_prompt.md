# 후쿠오카 텐진 쇼핑가이드 — 작업 이어가기 프롬프트

아래는 지금까지 만든 "후쿠오카 텐진 쇼핑 가이드" 모바일 웹앱(HTML 단일 파일) 작업 내역이야.
이 내용을 참고해서 이어서 작업해줘. (기존 파일을 업로드할 예정이면 그 파일 기준으로, 없으면 아래 스펙대로 처음부터 재현해줘.)

## 프로젝트 개요
- **결과물**: `fukuoka_guide.html` 단일 HTML 파일 (외부 서버/빌드 없이 인터넷 연결만 있으면 브라우저에서 바로 동작)
- **용도**: 후쿠오카 텐진 지역 쇼핑 스팟 가이드 + 체크리스트 + 추천 동선 계산 + 지도
- **원본 출처**: 네이버 카페 <체크인데이&일본여행> "2026최신! 후쿠오카 쇼핑 가이드" 글 기반, 이후 사용자 요청으로 매장/브랜드 대거 확장
- **톤앤매너**: 다정한 반말, 친구가 알려주는 듯한 말투 ("~야", "~해줄게" 등)
- **디자인 시스템**: Figma 브랜드 스타일 적용 완료
  - 색상: 네이비 `#191A23`(히어로/버튼), 라임 `#E0FE6B`(체크리스트 블록), 라벤더 `#E4DBFF`(지도 블록), 퍼플 `#A259FF`(포인트/마커), 크림 `#FCFCFC`(배경)
  - 폰트: Pretendard, 크기보다 **font-weight(700~800)로 위계** 표현
  - 버튼: 전부 완전한 필(pill) 모양, 검정+라임 배색
  - 섹션마다 통짜 컬러 블록 배경 사용 (그라데이션 지양)

## 기술 스택 / 구조
- 순수 HTML+CSS+JS, 프레임워크 없음
- 지도: Leaflet.js (`cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/`) + OpenStreetMap 타일
- 폰트: Google Fonts Pretendard + jsdelivr pretendard CDN
- 데이터는 JS 배열(`const spots = [...]`)에 하드코딩 — 매장 14~18개, 각 매장 안에 `floors` 배열로 층별 입점 브랜드 목록

## 핵심 기능 (전부 구현 완료)
1. **내 위치 켜기**: `navigator.geolocation`으로 현재 위치 요청 → 지도에 표시 + 각 매장까지 거리(m/km) 계산해서 카드에 표시
   - ⚠️ 알려진 제약: claude.ai artifact iframe 미리보기 안에서는 iOS Safari가 geolocation을 차단함(정책상 정상 동작 안 함). **실제 배포된 https 주소에서 열어야 정상 작동.**
2. **브랜드 단위 체크리스트**: 매장(건물) 단위가 아니라 **각 브랜드 하나하나**를 체크리스트 항목으로 나열 (총 87개+). 가나다순(`localeCompare(..., 'ko')`) 정렬.
3. **추천 동선 짜기 버튼**: 체크한 브랜드들을 기준으로,
   - 체크 안 한 매장 카드는 흐리게(dimmed) 처리
   - 체크한 브랜드가 있는 매장 카드는 테두리 강조 + 순서 배지(숫자) 표시
   - 카드 내부에서 **체크한 브랜드 이름만 노란/라임 형광펜 하이라이트**
   - 최근접 이웃(Nearest Neighbor) 알고리즘으로 최단 동선 계산 (내 위치 있으면 그 위치 기준, 없으면 텐진역 기준)
   - 상단에 "①→②→③" 순서 배너 + 총 이동거리·예상 도보시간 표시
4. **매장 이름 클릭** → 구글맵 **위치 검색**으로 연결 (길찾기 아님). Google Place ID 방식(`query_place_id` 파라미터)을 우선 사용해서 좌표 숫자 대신 **실제 장소명이 뜨도록** 처리. place_id 없는 항목만 좌표 검색으로 폴백.
5. **브랜드 이름 클릭**도 각각 개별 구글맵 링크로 연결 (브랜드별로 정확한 place_id를 직접 조사해서 매핑, 67개 이상 확보됨)
6. **"여기로 가기" 버튼**은 길찾기(dir) 링크 유지 (매장 이름 클릭과 용도 구분)
7. 체크리스트 항목 옆 📍 아이콘 버튼은 **삭제됨** (지저분하다는 피드백으로 제거, 클릭 기능은 이름 자체와 층별 브랜드 텍스트에만 남음)

## 현재 등록된 매장 목록 (18곳, id 순서)
1. 미나텐진 (MiNA Tenjin)
2. 원후쿠오카빌딩 (One Fukuoka Building) — sub: 파타고니아
3. 파르코 (Fukuoka PARCO) — sub: 호카
4. 비오로 (VIORO)
5. 솔라리아 플라자 (Solaria Plaza)
6. 이와타야 백화점 (Iwataya Dept. Store)
7. 노스페이스 (다이묘 거리 시작)
8. 휴먼메이드
9. 나나미카
10. 슈프림
11. 스투시
12. ABC-MART GRAND STAGE
13. 2nd STREET (세컨드스트리트)
14. 오클리 스토어
15. 돈키호테 텐진니시도리점
16. 르라보 후쿠오카
17. 베이프 스토어 후쿠오카
18. Ball&Chain FUKUOKA (텐진 지하상가)

각 매장 객체 구조:
```js
{
  id, name, en,
  lat, lng,
  addr, access, hours, walk,
  floors: [ { floor:"1F", brands:["브랜드1","브랜드2"], badge:"선택적 배지문구" } ],
  note: "다정한 반말 팁",
  sub: { title, brand, desc }  // 선택적, 근처 추가 스팟
}
```

## 데이터 조사 방식 (재현 시 참고)
- 매장 좌표: `places_search` 도구로 실제 Google Place 검색 → 정확한 lat/lng, place_id 확보
- 브랜드 좌표: 각 브랜드를 매장명과 함께 검색해서 개별 place_id 조사 (예: "유니클로 미나텐진 UNIQLO Mina Tenjin"), `brandCoords`(좌표)와 `brandPlaceIds`(place_id) 두 객체에 매핑
- place_id 있으면 `query_place_id` 파라미터로 이름이 뜨는 링크 생성, 없으면 좌표 기반 검색으로 폴백

## 지금까지 진행 이력 요약 (시간순)
1. 네이버 카페 글 2개(전국 브랜드 총정리 + 후쿠오카 텐진 가이드) 업로드받아 텐진 동선 PDF 제작
2. 같은 내용으로 모바일 반응형 HTML 페이지 제작 (지도+내 위치+길찾기, 다정한 반말)
3. 체크리스트(건물 단위) + 형광펜 강조 + 추천 동선 짜기 기능 추가
4. 브랜드 단위로 체크리스트 세분화 (건물 → 개별 브랜드 82개+)
5. 다이묘 거리를 개별 매장으로 분할(7개), 슈프림/스투시 추가 → 총 14곳
6. 브랜드 체크리스트 가나다순 정렬, 매장이름 클릭 시 구글맵 연결(처음엔 길찾기 → 위치검색으로 수정)
7. 브랜드명도 개별 클릭 가능하게, 좌표 대신 정확한 Place ID로 이름이 뜨도록 개선
8. 체크리스트 옆 📍 아이콘 버튼 삭제 (지저분하다는 피드백)
9. Figma 브랜드 디자인 시스템 적용 (색상/폰트/버튼 전면 개편)
10. 사용자 제공 구글맵 링크 기반으로 돈키호테 텐진니시도리점, 르라보 후쿠오카, 베이프 스토어 후쿠오카 추가 → 17곳
11. Ball&Chain FUKUOKA 추가 → 18곳 (현재 최신 상태)
12. (2026-07-15) 배포 준비: `site/` 폴더 생성 — `index.html`(v9 + 메타태그/OG태그 + AdSense 스크립트 주석 자리 + 푸터에 개인정보처리방침 링크), `privacy.html`(개인정보처리방침, 동일 디자인 시스템), `ads.txt`(게시자 ID 플레이스홀더). Vercel CLI(npx vercel) 디바이스 로그인 방식으로 배포 진행.
13. (2026-07-15) **Vercel 프로덕션 배포 완료**: https://fukuoka-tenjin-guide.vercel.app (Vercel 계정 mycenote2, 프로젝트 fukuoka-tenjin-guide). 메인/방침/ads.txt 모두 200 확인. 이후 수정 시 `cd site && npx vercel deploy --prod --yes`로 재배포.
14. (2026-07-15) 히어로 메인 타이틀에 부제 "-텐진, 다이묘거리 편-" 추가 (라임색, `.edition` 클래스), 문의 이메일 mycenote2@gmail.com으로 변경 → 재배포. ※ 이 변경은 `site/index.html`에만 반영, v9 원본은 보존용이라 그대로.
15. (2026-07-15) git 저장소 초기화(main 브랜치) 후 초기 커밋. **브랜드 요청 게시판** 추가: `site/board.html`(작성 폼: 브랜드명 필수 + 희망 지역 필 버튼[텐진/하카타/캐널시티/기타] + 한마디, 익명, 요청 목록 표시) + `site/api/requests.js`(Vercel 서버리스 함수, 허니팟 + IP당 10분 5회 제한, 목록 500개 유지). 메인 페이지 하단에 게시판 CTA 블록 + 푸터 링크 추가, 개인정보처리방침에 게시판 항목 신설.
16. (2026-07-15) **게시판 활성화 완료**: 사용자가 Vercel Storage에서 Redis 연결(환경변수 `REDIS_URL`만 제공, 민감 변수라 CLI로 값 조회 불가). REST 방식이 "fetch failed"로 실패해서 **ioredis TCP 클라이언트로 전환** (`site/package.json`에 ioredis 의존성 추가). 운영자 삭제 기능 추가: `DELETE /api/requests` + `x-admin-key` 헤더 (키는 Vercel 환경변수 `ADMIN_KEY`, Production 전용). 작성→조회→403차단→운영자삭제 전체 검증 완료. 게시판 라이브: https://fukuoka-tenjin-guide.vercel.app/board.html
17. (2026-07-15) **구글 서치 콘솔 인증(meta 태그 방식)**: `site/index.html` head에 `<meta name="google-site-verification" content="v-cacRXZNzojdXf3cee2HqJwq8aWHi_TNYVF5reFA7w">` 추가 후 재배포. ※ DNS TXT 방식은 vercel.app 서브도메인이라 불가(도메인 소유권 없음) → URL 접두어(URL prefix) 속성 + HTML 태그 방식으로 안내. **AdSense는 vercel.app 서브도메인으로는 승인 어려울 수 있음 → 커스텀 도메인 구입이 근본 해결책**(구입은 결제라 사용자가 직접, 이후 Vercel 도메인 연결·DNS TXT는 지원 가능).

## 알려진 이슈 / 참고사항
- Claude.ai artifact 공유 시 "previously unpublished" 에러가 한 번 발생했음 → 파일명을 바꿔서 새로 공유하면 우회 가능
- 컨테이너 네트워크 제약으로 cdnjs/unpkg 등 CDN에 직접 접근 불가 → 테스트 시 npm으로 leaflet 패키지 받아서 로컬 파일로 치환 후 playwright로 검증하는 방식 사용 중
- 실사용(체크박스 동작, geolocation 등)은 반드시 배포된 https 환경에서 최종 확인 필요

## 파일 구조 (2026-07-15 기준)
- `fukuoka_텐진_쇼핑가이드_v9.html` — 원본 최신본 (보존용)
- `site/index.html` — 배포용 (v9 + SEO 메타태그 + AdSense 자리 + 푸터 방침 링크)
- `site/privacy.html` — 개인정보처리방침 (문의: mycenote2@gmail.com)
- `site/ads.txt` — AdSense 게시자 ID 발급 후 주석 해제 필요

## 배포 정보 (2026-07-15)
- **라이브 URL**: https://fukuoka-tenjin-guide.vercel.app
- Vercel 계정: mycenote2 / 프로젝트: fukuoka-tenjin-guide
- 재배포: `cd site && npx vercel deploy --prod --yes`

## 다음에 이어서 할 수 있는 작업 예시
- Google AdSense 신청 (https://adsense.google.com) → 게시자 ID 발급되면 `ads.txt` 주석 해제 + `index.html` head의 AdSense 스크립트 주석 해제 → 재배포
- 다른 지역(하카타역, 캐널시티 등) 가이드 추가
- 추가 매장/브랜드 요청 시 위 "데이터 조사 방식"대로 place_id 조사 후 반영

---
이 프롬프트 아래에 이어서 요청사항을 적어줘.
