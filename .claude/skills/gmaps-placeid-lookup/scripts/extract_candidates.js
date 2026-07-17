/* 구글맵 검색 결과에서 매장 후보를 추출한다.
 *
 * 쓰는 법: 브라우저로 https://www.google.com/maps/search/<브랜드>+<지역> 를 연 뒤,
 *   javascript_tool 로 이 파일 내용을 통째로 실행한다. (async 즉시실행이라 결과가 바로 반환됨)
 *
 * 반환:
 *   { mode:'list'|'place'|'empty', query, count, results:[{name, ftid, text}] }
 *   - ftid 는 각 결과 href 의 `!1s0x...:0x...` (반드시 !1s). 이걸 ftid_to_placeid.py 로 ChIJ 변환.
 *   - text 는 카드 요약(주소·층·영업시간 등). 클로드가 읽고 지점명/주소를 정리한다.
 *
 * 두 경우를 모두 처리:
 *   - list : 여러 매장이 매치돼 결과 피드가 뜬 경우 → 피드를 끝까지 스크롤해 전부 수집.
 *   - place: 한 곳만 매치돼 /maps/place/ 단일 페이지로 리다이렉트된 경우 → 그 한 곳만.
 */
(async () => {
  const clean = (el) => {
    if (!el) return '';
    const drop = /^(웹사이트|경로|저장|공유|전화|리뷰|사진|Website|Directions|Save|Share|Call)$/;
    return el.innerText.split('\n').map(s => s.trim())
      .filter(s => s && !drop.test(s) && s !== '·')
      .join(' · ').replace(/\s·\s·\s/g, ' · ').slice(0, 200);
  };
  const ftidOf = (href) => (href.match(/!1s(0x[0-9a-f]+:0x[0-9a-f]+)/) || [])[1] || null;

  const feed = document.querySelector('[role="feed"]');
  if (feed) {
    // 결과 피드를 끝까지 스크롤해 지연 로드분까지 다 불러온다.
    let last = -1, stable = 0;
    for (let i = 0; i < 30 && stable < 3; i++) {
      feed.scrollTop = feed.scrollHeight;
      await new Promise(r => setTimeout(r, 700));
      const n = feed.querySelectorAll('a[href*="/maps/place/"]').length;
      if (n === last) stable++; else { stable = 0; last = n; }
    }
    const seen = new Set(), results = [];
    feed.querySelectorAll('a[href*="/maps/place/"]').forEach(a => {
      const ftid = ftidOf(a.href);
      const name = (a.getAttribute('aria-label') || '').trim();
      const key = ftid || name;
      if (!name || seen.has(key)) return;
      seen.add(key);
      const card = a.closest('[role="feed"] > div') || a.parentElement;
      results.push({ name, ftid, text: clean(card) });
    });
    return { mode: 'list', query: decodeURIComponent(location.pathname.split('/maps/search/')[1] || ''),
             count: results.length, results };
  }

  // 단일 매장 리다이렉트: 피드가 없다. location.href / HTML 에서 하나만 뽑는다.
  const html = document.documentElement.innerHTML;
  const ftid = (location.href.match(/!1s(0x[0-9a-f]+:0x[0-9a-f]+)/) || html.match(/!1s(0x[0-9a-f]+:0x[0-9a-f]+)/) || [])[1] || null;
  const name = (document.querySelector('h1')?.innerText || document.title.replace(/ - Google.*/,'')).trim();
  if (ftid) return { mode: 'place', query: name, count: 1,
                     results: [{ name, ftid, text: clean(document.querySelector('[role="main"]')) }] };
  return { mode: 'empty', query: location.href, count: 0, results: [] };
})()
