"use strict";

const POLL_MS = 5000;
const AXES = ["EDGE", "FLOW", "STRUCTURE", "SAFETY", "TIMING"];
const zoneCache = {};
const decided = new Set();

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") node.className = v;
    else if (k === "style") node.style.cssText = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined) continue;
    node.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(String(c)) : c);
  }
  return node;
}

const fmt = (n, d = 2) => (n === null || n === undefined ? "-" : Number(n).toFixed(d));
const won = (n) => Number(n).toLocaleString("ko-KR");

async function getJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  const body = await res.json();
  if (!body.ok) throw new Error(body.error || `app.js: ${url} failed`);
  return body.data;
}

async function decide(symbol, timestamp, action) {
  const res = await fetch("/api/decision", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, timestamp, action }),
  });
  const body = await res.json();
  if (!body.ok) throw new Error(body.error);
  decided.add(`${symbol}|${timestamp}`);
  refresh();
}

function axesView(scores) {
  return el("div", { class: "axes" }, AXES.map((a) =>
    el("div", { class: "axis" },
      el("span", {}, a),
      el("div", { class: "track" }, el("div", { class: "fill", style: `width:${Math.max(0, Math.min(100, scores[a] || 0))}%` })),
      el("span", { class: "num" }, fmt(scores[a], 1)))));
}

function stripView(recent) {
  return el("div", { class: "strip", title: "최근 프레임: 초록 = 통계적 유의 구간" },
    recent.map((f) => el("span", { class: f.zone.significant ? "sig" : "", title: `${f.timestamp} ${f.zone.significant ? "유의" : "비유의"}` })));
}

function recommendationView(symbol, latest) {
  if (!latest || !latest.zone.significant || latest.warmup) return null;
  const key = `${symbol}|${latest.timestamp}`;
  const opened = latest.opened.length > 0;
  return el("div", { class: "rec" },
    el("p", {}, `유의 구간 진입: ${latest.zone.zones.join(" · ")}`),
    el("p", { class: "small" }, opened ? "이번 봉에서 가상 롱 포지션이 열렸습니다. 실제로 따라 샀는지 기록하세요." : "구간 안이지만 이번 봉에서 새 가상 진입은 없습니다(보유 중/쿨다운)."),
    decided.has(key)
      ? el("p", { class: "small" }, "기록됨")
      : el("div", {},
          el("button", { onclick: () => decide(symbol, latest.timestamp, "follow").catch(showError) }, "따라함"),
          el("button", { onclick: () => decide(symbol, latest.timestamp, "skip").catch(showError) }, "스킵")));
}

function tradesTable(trades) {
  if (!trades.length) return el("p", { class: "small" }, "없음");
  return el("div", { class: "scroll" }, el("table", {},
    el("thead", {}, el("tr", {}, ["진입", "청산", "진입가", "청산가", "순수익%", "사유"].map((h) => el("th", {}, h)))),
    el("tbody", {}, trades.slice().reverse().map((t) => el("tr", {},
      el("td", {}, (t.entry_time || "").slice(5, 16)),
      el("td", {}, (t.exit_time || "보유중").slice(5, 16)),
      el("td", {}, won(t.entry_raw_price)),
      el("td", {}, t.exit_raw_price ? won(t.exit_raw_price) : "-"),
      el("td", {}, fmt(t.net_return_pct, 3)),
      el("td", {}, t.close_reason || "-"))))));
}

function zonesView(z) {
  if (!z) return el("p", { class: "small" }, "구간 보고서 불러오는 중…");
  const sig = z.zones.filter((x) => x.status === "significant").length;
  return el("div", {},
    el("p", { class: "small" },
      `학습 ${z.train.frames}프레임(${(z.train.from || "").slice(0, 10)}~${(z.train.to || "").slice(0, 10)}) · 검증 ${z.holdout.frames}프레임 · ` +
      `왕복비용 ${fmt(2 * (z.costs.fee_bps_per_side + z.costs.slippage_bps_per_side) / 100, 2)}% · 후보 ${z.total}개 중 유의 ${sig}개`),
    el("p", { class: "small" }, z.method),
    el("div", { class: "scroll" }, el("table", {},
      el("thead", {}, el("tr", {}, ["구간", "학습 n", "학습 평균%", "학습 p", "검증 n", "검증 평균%", "판정"].map((h) => el("th", {}, h)))),
      el("tbody", {}, z.zones.slice(0, 12).map((x) => el("tr", {},
        el("td", {}, x.name.replace("zone:", "")),
        el("td", {}, x.train_n),
        el("td", {}, fmt(x.train_mean_pct, 3)),
        el("td", {}, fmt(x.train_p, 3)),
        el("td", {}, x.holdout_n),
        el("td", {}, fmt(x.holdout_mean_pct, 3)),
        el("td", {}, x.status === "significant" ? "유의" : x.reason)))))));
}

function symbolCard(code, s, jevEnabled) {
  const latest = s.latest;
  const zoneBadge = !latest ? el("span", { class: "badge warn" }, "데이터 대기")
    : latest.zone.significant ? el("span", { class: "badge sig" }, "통계적 유의 구간")
    : el("span", { class: "badge nosig" }, "비유의 구간 · 거래 안 함");
  return el("section", { class: "card" },
    el("div", { class: "head" },
      el("h2", {}, code),
      latest ? el("span", { class: "price" }, won(latest.price)) : null,
      zoneBadge,
      s.significant_zone_count === 0 ? el("span", { class: "badge warn" }, "유의 구간 0개 → 이 종목은 거래하지 않음") : null),
    s.error ? el("p", { class: "error" }, `폴링 오류: ${s.error}`) : null,
    latest ? el("p", { class: "small" },
      `마지막 봉 ${latest.timestamp} · 신호 ${latest.signals.join(", ")} · Jev ${jevEnabled ? (latest.jev ? "원시확률(보정 전)" : "응답 없음") : "꺼짐(키 없음)"}`) : null,
    latest ? axesView(latest.scores) : null,
    latest ? el("p", { class: "small" }, `측정 안 된 항목(Unknown, 중립값 사용): ${latest.unmeasured.join(", ")}`) : null,
    stripView(s.recent),
    recommendationView(code, latest),
    el("h3", {}, "가상 포지션 / 최근 청산"),
    tradesTable([...s.open_trades, ...s.closed_trades]),
    s.performance.length ? el("p", { class: "small" }, s.performance.map((p) =>
      `${p.pattern}: ${p.trades}회 승률 ${fmt(p.win_rate * 100, 1)}% 평균 ${fmt(p.average_return_pct, 3)}%`).join(" / ")) : null,
    el("h3", {}, "통계적 구간 판정"),
    zonesView(zoneCache[code]));
}

function showError(err) {
  document.getElementById("meta").textContent = `오류: ${err.message}`;
}

async function refresh() {
  try {
    const data = await getJson("/api/state");
    const codes = Object.keys(data.symbols);
    await Promise.all(codes.filter((c) => !zoneCache[c]).map(async (c) => { zoneCache[c] = await getJson(`/api/zones?symbol=${encodeURIComponent(c)}`); }));
    document.getElementById("meta").textContent =
      `마지막 조회 ${data.last_poll || "-"} · 주기 ${data.interval}s · 텔레그램 ${data.telegram_enabled ? "켜짐" : "꺼짐"}`;
    const root = document.getElementById("symbols");
    root.replaceChildren(...codes.map((c) => symbolCard(c, data.symbols[c], data.jev_enabled)));
  } catch (err) {
    showError(err);
  }
}

refresh();
setInterval(refresh, POLL_MS);
