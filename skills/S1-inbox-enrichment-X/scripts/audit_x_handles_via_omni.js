#!/usr/bin/env node

const fs = require("fs");
const http = require("http");
const path = require("path");

let seq = 0;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function req(requestPath, method = "GET") {
  return new Promise((resolve, reject) => {
    const r = http.request(
      { hostname: "127.0.0.1", port: 9222, path: requestPath, method },
      (res) => {
        let body = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => resolve({ status: res.statusCode, body }));
      }
    );
    r.on("error", reject);
    r.end();
  });
}

async function cdp(wsUrl, expression, waitMs = 5000) {
  const ws = new WebSocket(wsUrl);
  const pending = new Map();
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    }
  };
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });
  const send = (method, params = {}) =>
    new Promise((resolve) => {
      const id = ++seq;
      pending.set(id, resolve);
      ws.send(JSON.stringify({ id, method, params }));
    });
  await send("Page.enable");
  await send("Runtime.enable");
  await sleep(waitMs);
  const res = await send("Runtime.evaluate", {
    expression,
    returnByValue: true,
  });
  ws.close();
  return res?.result?.result?.value;
}

async function openAndEval(url, expression, waitMs = 5000) {
  const created = await req("/json/new?" + encodeURIComponent(url), "PUT");
  const target = JSON.parse(created.body);
  const raw = await cdp(target.webSocketDebuggerUrl, expression, waitMs);
  try {
    return JSON.parse(raw);
  } catch (_error) {
    return { __raw: raw };
  }
}

function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function scoreHit(name, hit) {
  const target = normalizeText(name);
  const block = normalizeText((hit.block || "") + " " + (hit.text || ""));
  let score = 0;
  if (!block) return score;
  if (block.includes(target) && target) score += 5;
  const tokens = target.split(" ").filter(Boolean);
  for (const token of tokens) {
    if (token.length >= 3 && block.includes(token)) score += 1;
  }
  return score;
}

function classify(name, hits) {
  const filtered = (hits || []).filter((hit) => hit && hit.handle);
  if (!filtered.length) {
    return { suggested_handle: "", confidence: "low", reason: "X people search 无结果" };
  }
  const ranked = filtered
    .map((hit) => ({ ...hit, score: scoreHit(name, hit) }))
    .sort((a, b) => b.score - a.score);

  const top = ranked[0];
  const second = ranked[1];
  let confidence = "low";
  if (top.score >= 6) confidence = "high";
  else if (top.score >= 3) confidence = "medium";
  if (second && top.score - second.score <= 1 && confidence === "high") {
    confidence = "medium";
  }

  return {
    suggested_handle: top.handle,
    confidence,
    reason: `top_score=${top.score}` + (second ? `, second_score=${second.score}` : ""),
    top_hits: ranked.slice(0, 5),
  };
}

async function main() {
  const [, , inputJson, outputJson] = process.argv;
  if (!inputJson || !outputJson) {
    console.error("Usage: audit_x_handles_via_omni.js <input.json> <output.json>");
    process.exit(1);
  }
  const rows = JSON.parse(fs.readFileSync(inputJson, "utf8"));
  const out = [];
  for (const row of rows) {
    const searchUrl = `https://x.com/search?q=${encodeURIComponent(row.name)}&src=typed_query&f=user`;
    const expr = `JSON.stringify((() => {
      const anchors = [...document.querySelectorAll('a[href]')];
      const hits = [];
      const seen = new Set();
      for (const a of anchors) {
        const href = a.getAttribute('href') || '';
        if (!href.startsWith('/')) continue;
        const cell = a.closest('[data-testid="UserCell"]');
        if (!cell) continue;
        const seg = href.slice(1).split('/')[0];
        if (!seg || seg.includes('?') || href.includes('/status/') || href.includes('/photo/')) continue;
        const handle = '@' + seg;
        if (seen.has(handle.toLowerCase())) continue;
        hits.push({
          handle,
          text: (a.innerText || a.textContent || '').trim().slice(0, 120),
          block: (cell.innerText || '').trim().slice(0, 320)
        });
        seen.add(handle.toLowerCase());
        if (hits.length >= 8) break;
      }
      return { title: document.title, hits };
    })())`;
    const page = await openAndEval(searchUrl, expr, 5500);
    const classified = classify(row.name, page.hits || []);
    out.push({
      old_handle: row.old_handle,
      name: row.name,
      notes: row.notes,
      ...classified,
      page_title: page.title || "",
    });
  }
  fs.writeFileSync(outputJson, JSON.stringify(out, null, 2), "utf8");
  console.log(outputJson);
  console.log(`written ${out.length}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
