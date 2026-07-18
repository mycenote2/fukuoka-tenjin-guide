const LIST_KEY = "brand_requests";
const AREAS = ["텐진", "하카타", "캐널시티", "시부야", "하라주쿠", "오모테산도", "신주쿠 동구", "신주쿠 서구", "가부키초", "기타"];
const REGIONS = ["fukuoka-tenjin", "shibuya", "shinjuku"];
// region 필드가 없는 레거시 글은 후쿠오카 텐진 요청으로 취급한다
const DEFAULT_REGION = "fukuoka-tenjin";

let client = null;
function getRedis() {
  const url =
    process.env.REDIS_URL || process.env.KV_URL || process.env.UPSTASH_REDIS_URL;
  if (!url) return null;
  if (!client) {
    const Redis = require("ioredis");
    client = new Redis(url, {
      maxRetriesPerRequest: 2,
      connectTimeout: 5000,
    });
    client.on("error", (e) => console.error("redis error:", e && e.message));
  }
  return client;
}

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  const redis = getRedis();
  if (!redis) {
    res.status(503).json({ error: "not_configured" });
    return;
  }

  try {
    if (req.method === "GET") {
      const raw = await redis.lrange(LIST_KEY, 0, 499);
      let items = (raw || [])
        .map((s) => {
          try { return JSON.parse(s); } catch { return null; }
        })
        .filter(Boolean);
      // ?region=shibuya 처럼 지역이 지정되면 그 지역 글만 (레거시 글은 기본 지역으로 간주)
      const region = String((req.query && req.query.region) || "").trim();
      if (region) {
        items = items.filter((it) => (it.region || DEFAULT_REGION) === region);
      }
      res.status(200).json({ items: items.slice(0, 200) });
      return;
    }

    if (req.method === "POST") {
      const body =
        typeof req.body === "object" && req.body !== null
          ? req.body
          : JSON.parse(req.body || "{}");

      // 봇이 채우는 숨김 필드: 채워져 있으면 저장 없이 성공한 척 응답
      if (String(body.website || "").trim() !== "") {
        res.status(200).json({ ok: true });
        return;
      }

      const brand = String(body.brand || "").trim();
      const comment = String(body.comment || "").trim();
      const area = AREAS.includes(body.area) ? body.area : "기타";
      const region = REGIONS.includes(body.region) ? body.region : DEFAULT_REGION;

      if (!brand) {
        res.status(400).json({ error: "brand_required" });
        return;
      }
      if (brand.length > 40 || comment.length > 200) {
        res.status(400).json({ error: "too_long" });
        return;
      }

      const ip =
        String(req.headers["x-forwarded-for"] || "").split(",")[0].trim() ||
        "unknown";
      const rlKey = `rl:${ip}`;
      const count = await redis.incr(rlKey);
      if (count === 1) await redis.expire(rlKey, 600);
      if (count > 5) {
        res.status(429).json({ error: "rate_limited" });
        return;
      }

      const item = {
        id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
        brand,
        comment,
        area,
        region,
        ts: Date.now(),
      };
      await redis.lpush(LIST_KEY, JSON.stringify(item));
      await redis.ltrim(LIST_KEY, 0, 499);
      res.status(200).json({ ok: true, item });
      return;
    }

    // 운영자 전용 삭제: x-admin-key 헤더가 ADMIN_KEY 환경변수와 일치해야 함
    if (req.method === "DELETE") {
      const adminKey = process.env.ADMIN_KEY;
      if (!adminKey || req.headers["x-admin-key"] !== adminKey) {
        res.status(403).json({ error: "forbidden" });
        return;
      }
      const body =
        typeof req.body === "object" && req.body !== null
          ? req.body
          : JSON.parse(req.body || "{}");
      const id = String(body.id || "").trim();
      if (!id) {
        res.status(400).json({ error: "id_required" });
        return;
      }
      const raw = await redis.lrange(LIST_KEY, 0, 499);
      const target = (raw || []).find((s) => {
        try { return JSON.parse(s).id === id; } catch { return false; }
      });
      if (!target) {
        res.status(404).json({ error: "not_found" });
        return;
      }
      await redis.lrem(LIST_KEY, 1, target);
      res.status(200).json({ ok: true });
      return;
    }

    res.status(405).json({ error: "method_not_allowed" });
  } catch (e) {
    console.error("requests api error:", e && e.message);
    res.status(500).json({ error: "server_error" });
  }
};
