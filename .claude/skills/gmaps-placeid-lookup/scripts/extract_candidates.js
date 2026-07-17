/* 구글맵 검색 결과에서 매장 후보 + 상세정보를 추출한다.
 *
 * 쓰는 법: 브라우저로 https://www.google.com/maps/search/<브랜드>+<지역> 를 연 뒤,
 *   javascript_tool 로 이 파일 내용을 통째로 실행한다. (async 즉시실행이라 결과가 바로 반환됨)
 *
 * 반환:
 *   { mode:'list'|'place'|'empty', query, count, results:[{
 *       name, ftid, addr, floor, category, hours, phone, plusCode, rating, reviews, text }] }
 *   - ftid : 각 결과 href 의 `!1s0x...:0x...` (반드시 !1s). ftid_to_placeid.py 로 ChIJ 변환.
 *   - addr : 구글맵 표기 주소(건물명 포함). floor : addr 에서 뽑은 층(구글맵 표기, 교차검증 필요).
 *   - text : 카드/상세 요약(폴백). 클로드가 읽고 지점명·주소를 사람이 알아보게 정리한다.
 *
 * 두 경우 모두 처리:
 *   - list : 여러 매장이 매치돼 결과 피드가 뜬 경우 → 피드를 끝까지 스크롤해 카드에서 필드 파싱.
 *   - place: 한 곳만 매치돼 /maps/place/ 단일 페이지로 리다이렉트된 경우 → 상세페이지 라벨 버튼에서 추출.
 */
(async () => {
  // 층 패턴: "地下2階", "B1", "B1F", "6F", "６Ｆ", "３, ４Ｆ"(선행 숫자·콤마 포함)
  const FL = /(地下\s*[0-9０-９]+\s*階|B[0-9]+\s*[FＦ]?|[0-9０-９][0-9０-９,，\s]*\s*(?:階|[FＦ]))/;
  const stripLabel = (s) => (s || '').replace(/^\s*(주소|전화(?:번호)?|플러스\s*코드|Plus\s*code|Phone|Address)\s*:\s*/i, '').trim();
  const floorOf = (a) => { const m = (a || '').match(FL); return m ? m[0].replace(/\s+/g, '') : null; };
  const ftidOf = (h) => (h.match(/!1s(0x[0-9a-f]+:0x[0-9a-f]+)/) || [])[1] || null;

  // 검색 결과 카드 1개 → 구조화 필드
  function parseCard(card, name) {
    const drop = /^(웹사이트|경로|저장|공유|주문|메뉴|예약|Website|Directions|Save|Share|Order|Menu|Book)$/;
    const lines = card.innerText.split('\n').map((s) => s.trim()).filter(Boolean)
      .filter((l) => l !== name && l !== '·' && !drop.test(l));
    const r = { rating: null, reviews: null, category: null, addr: null, floor: null, hours: null, phone: null, desc: null };
    for (const ln of lines) {
      const m = ln.match(/^([0-5][.,]\d)\s*(?:\((\d[\d,]*)\))?$/); // "4.0(661)"
      if (m && !r.rating) { r.rating = m[1]; r.reviews = m[2] || null; continue; }
      const ph = ln.match(/\+?\d[\d\-\s]{7,}\d/);
      if (/영업|24시간|휴무|정기|Open|Close/.test(ln)) { // 영업상태 · 시간 · 전화
        if (ph && !r.phone) r.phone = ph[0].trim();
        if (!r.hours) r.hours = ln.replace(/\s*·\s*\+?\d[\d\-\s]{7,}\d.*$/, '').trim();
        continue;
      }
      if (/·/.test(ln) && !r.addr) { // "카테고리 ·  · 주소(건물 층)"
        const parts = ln.split('·').map((s) => s.trim()).filter(Boolean);
        if (parts.length >= 2) { r.category = parts[0]; r.addr = parts[parts.length - 1]; }
        else r.category = r.category || parts[0];
        continue;
      }
      if (ph && ln.replace(ph[0], '').trim().length < 3) { if (!r.phone) r.phone = ph[0].trim(); continue; }
      if (!r.desc && !/^["'“]/.test(ln)) r.desc = ln;
    }
    r.floor = floorOf(r.addr);
    return r;
  }

  const feed = document.querySelector('[role="feed"]');
  if (feed) {
    let last = -1, stable = 0;
    for (let i = 0; i < 30 && stable < 3; i++) { // 지연 로드분까지 스크롤
      feed.scrollTop = feed.scrollHeight;
      await new Promise((r) => setTimeout(r, 700));
      const n = feed.querySelectorAll('a[href*="/maps/place/"]').length;
      if (n === last) stable++; else { stable = 0; last = n; }
    }
    const seen = new Set(), results = [];
    feed.querySelectorAll('a[href*="/maps/place/"]').forEach((a) => {
      const name = (a.getAttribute('aria-label') || '').trim();
      const ftid = ftidOf(a.href);
      const key = ftid || name;
      if (!name || seen.has(key)) return;
      seen.add(key);
      const card = a.closest('[role="feed"] > div') || a.parentElement;
      const text = card.innerText.split('\n').map((s) => s.trim()).filter(Boolean).join(' · ').slice(0, 200);
      results.push({ name, ftid, plusCode: null, ...parseCard(card, name), text });
    });
    return { mode: 'list', query: decodeURIComponent(location.pathname.split('/maps/search/')[1] || ''), count: results.length, results };
  }

  // place mode: 상세페이지의 라벨 버튼(data-item-id)에서 깔끔하게 추출
  const main = document.querySelector('[role="main"]') || document;
  const html = document.documentElement.innerHTML;
  const ftid = (location.href.match(/!1s(0x[0-9a-f]+:0x[0-9a-f]+)/) || html.match(/!1s(0x[0-9a-f]+:0x[0-9a-f]+)/) || [])[1] || null;
  const name = (main.querySelector('h1')?.textContent || document.title.replace(/ - Google.*/, '')).trim();
  const btn = (sel) => { const b = main.querySelector(sel); return b ? (b.getAttribute('aria-label') || b.textContent || '').trim() : null; };
  const addr = stripLabel(btn('button[data-item-id^="address"]')) || null;
  const phone = stripLabel(btn('button[data-item-id^="phone"]')) || null;
  const plusCode = stripLabel(btn('button[data-item-id="oloc"]')) || null;
  const category = btn('button[jsaction*="category"]') || null;
  const rating = (main.querySelector('.MW4etd')?.textContent || '').trim() || null;
  const hours = [...main.querySelectorAll('[aria-label]')].map((e) => e.getAttribute('aria-label'))
    .find((l) => /영업 종료|영업 중|24시간 영업|오전.*영업|오후.*영업|Opens|Closes/.test(l || '')) || null;
  if (ftid) {
    const text = (main.innerText || '').split('\n').map((s) => s.trim()).filter(Boolean).slice(0, 8).join(' · ').slice(0, 200);
    return { mode: 'place', query: name, count: 1, results: [{ name, ftid, addr, floor: floorOf(addr), category, hours, phone, plusCode, rating, reviews: null, text }] };
  }
  return { mode: 'empty', query: location.href, count: 0, results: [] };
})()
