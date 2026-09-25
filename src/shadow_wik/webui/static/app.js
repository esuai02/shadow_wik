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
const won = (n) => Number(n || 0).toLocaleString("ko-KR");

async function getJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  const body = await res.json();
  if (!body.ok) throw new Error(body.error || `app.js: ${url} failed`);
  return body.data;
}

async function postJson(url, data) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const body = await res.json();
  if (!body.ok) throw new Error(body.error || `app.js: ${url} failed`);
  return body.data;
}

async function decide(symbol, timestamp, action) {
  await postJson("/api/decision", { symbol, timestamp, action });
  decided.add(`${symbol}|${timestamp}`);
  refresh();
}

function validationLabel(level) {
  if (level === 0) return "탐색 모드";
  if (level < 35) return "느슨한 검증";
  if (level < 70) return "중간 검증";
  if (level < 90) return "강한 검증";
  return "매우 엄격";
}

async function setValidation(level) {
  const data = await postJson("/api/settings", { validation_level: Number(level) });
  document.getElementById("validationValue").textContent = data.validation_level;
  document.getElementById("validationMode").textContent = validationLabel(data.validation_level);
}

const slider = document.getElementById("validationSlider");
slider.addEventListener("input", () => {
  document.getElementById("validationValue").textContent = slider.value;
  document.getElementById("validationMode").textContent = validationLabel(Number(slider.value));
});
slider.addEventListener("change", () => setValidation(slider.value).catch(showError));

function axesView(scores) {
  return el("div", { class: "axes" }, AXES.map((a) =>
    el("div", { class: "axis" },
      el("span", {}, a),
      el("div", { class: "track" }, el("div", { class: "fill", style: `width:${Math.max(0, Math.min(100, scores[a] || 0))}%` })),
      el("span", { class: "num" }, fmt(scores[a], 1)))));
}

function stripView(recent) {
  return el("div", { class: "strip", title: "최근 프레임: 진한 칸 = Jev 단타 패턴 가상진입" },
    recent.map((f) => el("span", {
      class: f.pattern_entered ? "sig" : "",
      title: `${f.timestamp} ${f.pattern_entered ? "패턴 진입" : "관찰"}`,
    })));
}

function patternView(patterns) {
  if (!patterns || !patterns.length) {
    return el("p", { class: "small" }, "Jev 단타 패턴 데이터 없음");
  }
  return el("div", { class: "pattern-grid" }, patterns.map((p) =>
    el("div", { class: `pattern-row ${p.eligible ? "eligible" : ""}` },
      el("span", { class: "pattern-name" }, p.label),
      el("span", {}, `Jev ${p.probability === null || p.probability === undefined ? "-" : fmt(p.probability * 100, 1) + "%"}`),
      el("span", {}, `paper 강도 ${fmt(p.paper_evidence_strength, 0)}`),
      el("span", { class: "small" }, p.eligible ? "진입 가능" : (p.recognized ? "history gate 대기" : "미인식")))));
}

function recommendationView(symbol, latest) {
  if (!latest || latest.warmup) return null;
  const key = `${symbol}|${latest.timestamp}`;
  const opened = latest.opened || [];
  if (!opened.length) return null;
  return el("div", { class: "rec" },
    el("p", {}, `가상 진입: ${opened.map((x) => x.pattern).join(" · ")}`),
    el("p", { class: "small" }, "Jev 패턴 판별 + 현재 dashboard 검증 강도를 통과했습니다. 실제 주문과 무관한 paper 체결입니다."),
    decided.has(key)
      ? el("p", { class: "small" }, "관찰 기록됨")
      : el("div", {},
          el("button", { onclick: () => decide(symbol, latest.timestamp, "follow").catch(showError) }, "체감상 유효"),
          el("button", { onclick: () => decide(symbol, latest.timestamp, "skip").catch(showError) }, "체감상 무효")));
}

function tradesTable(trades) {
  if (!trades.length) return el("p", { class: "small" }, "없음");
  return el("div", { class: "scroll" }, el("table", {},
    el("thead", {}, el("tr", {}, ["패턴", "진입", "청산", "진입가", "청산가", "순수익%", "사유"].map((h) => el("th", {}, h)))),
    el("tbody", {}, trades.slice().reverse().map((t) => el("tr", {},
      el("td", {}, t.pattern),
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
      `참고용 통계 zone · 학습 ${z.train.frames}프레임 · 검증 ${z.holdout.frames}프레임 · 후보 ${z.total}개 중 유의 ${sig}개`),
    el("div", { class: "scroll" }, el("table", {},
      el("thead", {}, el("tr", {}, ["구간", "학습 n", "학습 평균%", "학습 p", "검증 n", "검증 평균%", "판정"].map((h) => el("th", {}, h)))),
      el("tbody", {}, z.zones.slice(0, 8).map((x) => el("tr", {},
        el("td", {}, x.name.replace("zone:", "")),
        el("td", {}, x.train_n),
        el("td", {}, fmt(x.train_mean_pct, 3)),
        el("td", {}, fmt(x.train_p, 3)),
        el("td", {}, x.holdout_n),
        el("td", {}, fmt(x.holdout_mean_pct, 3)),
        el("td", {}, x.status === "significant" ? "유의" : x.reason)))))));
}

function portfolioView(p) {
  if (!p) return el("p", { class: "small" }, "포트폴리오 대기");
  return el("div", {},
    el("div", { class: "portfolio-head" },
      el("div", {}, el("span", { class: "small" }, "시드"), el("strong", {}, `${won(p.seed_krw)}원`)),
      el("div", {}, el("span", { class: "small" }, "현재 equity"), el("strong", {}, `${won(p.equity_krw)}원`)),
      el("div", {}, el("span", { class: "small" }, "수익률"), el("strong", {}, `${fmt(p.return_pct, 3)}%`)),
      el("div", {}, el("span", { class: "small" }, "현금"), el("strong", {}, `${won(p.cash_krw)}원`)),
      el("div", {}, el("span", { class: "small" }, "포지션"), el("strong", {}, `${p.open_positions}/${p.max_positions}`))),
    el("p", { class: "small" }, `패턴당 ${won(p.per_trade_krw)}원 · 실현손익 ${won(p.realized_pnl_krw)}원 · 청산 ${p.closed_trades}회 · 레버리지 없음`));
}

function symbolCard(code, s, jevEnabled) {
  const latest = s.latest;
  const modeBadge = s.paper_mode === "jev_scalp"
    ? el("span", { class: "badge sig" }, "Jev 단타패턴")
    : el("span", { class: "badge warn" }, "통계 zone fallback");
  return el("section", { class: "card" },
    el("div", { class: "head" },
      el("h2", {}, code),
      latest ? el("span", { class: "price" }, won(latest.price)) : null,
      modeBadge),
    s.error ? el("p", { class: "error" }, `폴링 오류: ${s.error}`) : null,
    latest ? el("p", { class: "small" },
      `마지막 봉 ${latest.timestamp} · 신호 ${latest.signals.join(", ")} · Jev ${jevEnabled ? (latest.jev ? "패턴 판별 활성" : "응답 없음") : "꺼짐(키 없음)"}`) : null,
    latest ? axesView(latest.scores) : null,
    latest ? patternView(latest.patterns) : null,
    latest ? el("p", { class: "small" }, `측정 안 된 항목: ${latest.unmeasured.join(", ")}`) : null,
    stripView(s.recent),
    recommendationView(code, latest),
    el("h3", {}, "가상 포지션 / 최근 청산"),
    tradesTable([...s.open_trades, ...s.closed_trades]),
    s.performance.length ? el("p", { class: "small" }, s.performance.map((p) =>
      `${p.pattern}: ${p.trades}회 승률 ${fmt(p.win_rate * 100, 1)}% 평균 ${fmt(p.average_return_pct, 3)}%`).join(" / ")) : null,
    el("h3", {}, "참고용 기존 통계 zone"),
    zonesView(zoneCache[code]));
}

function showError(err) {
  document.getElementById("meta").textContent = `오류: ${err.message}`;
}

async function refresh() {
  try {
    const data = await getJson("/api/state");
    const codes = Object.keys(data.symbols);
    await Promise.all(codes.filter((c) => !zoneCache[c]).map(async (c) => {
      zoneCache[c] = await getJson(`/api/zones?symbol=${encodeURIComponent(c)}`);
    }));

    document.getElementById("meta").textContent =
      `마지막 조회 ${data.last_poll || "-"} · 주기 ${data.interval}s · Jev ${data.jev_enabled ? "켜짐" : "꺼짐"} · 텔레그램 ${data.telegram_enabled ? "켜짐" : "꺼짐"}`;

    const level = Number(data.validation_level || 0);
    if (document.activeElement !== slider) slider.value = level;
    document.getElementById("validationValue").textContent = level;
    document.getElementById("validationMode").textContent = validationLabel(level);
    document.getElementById("portfolio").replaceChildren(portfolioView(data.portfolio));

    const root = document.getElementById("symbols");
    root.replaceChildren(...codes.map((c) => symbolCard(c, data.symbols[c], data.jev_enabled)));
  } catch (err) {
    showError(err);
  }
}

refresh();
setInterval(refresh, POLL_MS);
