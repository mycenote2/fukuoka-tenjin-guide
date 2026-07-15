const LIST_KEY = "brand_requests";
const AREAS = ["텐진", "하카타", "캐널시티", "기타"];

function redisConfig() {
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return null;
  return { url, token };
}

async function redis(cfg, command) {
  const r = await fetch(cfg.url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${cfg.token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(command),
  });
  if (!r.ok) throw new Error(`redis ${r.status}`);
  const data = await r.json();
  return data.result;
}

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  const cfg = redisConfig();
  if (!cfg) {
    res.status(503).json({ error: "not_configured" });
    return;
  }

  try {
    if (req.method === "GET") {
      const raw = await redis(cfg, ["LRANGE", LIST_KEY, "0", "199"]);
      const items = (raw || [])
        .map((s) => {
          try { return JSON.parse(s); } catch { return null; }
        })
        .filter(Boolean);
      res.status(200).json({ items });
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
      const count = await redis(cfg, ["INCR", rlKey]);
      if (count === 1) await redis(cfg, ["EXPIRE", rlKey, "600"]);
      if (count > 5) {
        res.status(429).json({ error: "rate_limited" });
        return;
      }

      const item = {
        id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
        brand,
        comment,
        area,
        ts: Date.now(),
      };
      await redis(cfg, ["LPUSH", LIST_KEY, JSON.stringify(item)]);
      await redis(cfg, ["LTRIM", LIST_KEY, "0", "499"]);
      res.status(200).json({ ok: true, item });
      return;
    }

    res.status(405).json({ error: "method_not_allowed" });
  } catch (e) {
    res.status(500).json({ error: "server_error" });
  }
};
