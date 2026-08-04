// Search page (RAG): call /answer, render each status as its own readable card.
// Speaks the customer's language — never shows field names, JSON, or errors.

const qEl = document.getElementById("q");
const askBtn = document.getElementById("ask");
const answerEl = document.getElementById("answer");

const COPY = {
  empty:    "Type a question to begin — try one of the examples above.",
  no_match: "No family office in our data matches that. Try broader terms, or ask about type, location, AUM, or recent activity.",
  error:    "Momentarily unavailable — this is on our side, not your question. Please try again in a moment.",
};

// The real second-model (LLM-2 validator) outcome, shown — not asserted.
const VERDICT_BADGE = {
  approved: "A second AI checks each answer against the records before you see it.",
  refined:  "✎ Second AI corrected this — trimmed to only what the records support",
  declined: "⦸ Second AI held this back — the records didn't fully support it",
};

function card(status, text, sources, verdict) {
  const el = document.createElement("div");
  el.className = "card " + status;
  const p = document.createElement("p");
  p.className = "text";
  p.textContent = text;               // textContent keeps it safe from HTML injection;
  p.style.whiteSpace = "pre-wrap";    // pre-wrap makes the bullet/numbered newlines show
  el.appendChild(p);

  // Show the second model's actual decision on any answered/declined result.
  if (status === "answered" || status === "declined") {
    const meta = document.createElement("div");
    meta.className = "meta";
    if (status === "answered") {
      const n = (sources || []).length;
      const based = document.createElement("span");
      based.className = "based";
      based.textContent = n ? `Top ${n} most-relevant record${n > 1 ? "s" : ""} searched:` : "";
      meta.appendChild(based);
      (sources || []).forEach(s => {
        const c = document.createElement("span");
        c.className = "srcchip";
        c.textContent = s;
        meta.appendChild(c);
      });
    }
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = VERDICT_BADGE[verdict] || VERDICT_BADGE[status] || "";
    meta.appendChild(badge);
    el.appendChild(meta);
  }
  answerEl.replaceChildren(el);
}

function setLoading(on) {
  askBtn.disabled = on;
  qEl.disabled = on;
  askBtn.textContent = on ? "Thinking…" : "Ask";
}

async function ask(query) {
  const q = (query || "").trim();
  if (!q) { card("empty", COPY.empty); return; }
  setLoading(true);
  try {
    const r = await fetch("/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q }),
    });
    if (!r.ok) throw new Error("bad status");
    const d = await r.json();
    const status = d.status || (d.verdict === "declined" ? "declined" : "answered");
    let text = d.text;
    if (status === "no_match") text = COPY.no_match;
    if (status === "error") text = COPY.error;
    card(status, text, d.sources, d.verdict);   // show the second model's real verdict
  } catch (e) {
    card("error", COPY.error);
  } finally {
    setLoading(false);
  }
}

askBtn.addEventListener("click", () => ask(qEl.value));
qEl.addEventListener("keydown", e => { if (e.key === "Enter") ask(qEl.value); });
document.getElementById("examples").addEventListener("click", e => {
  if (e.target.classList.contains("chip")) { qEl.value = e.target.textContent; ask(qEl.value); }
});

// honest, dynamic corpus size + type breakdown (no hard-coded number, so the
// header stays true as the corpus grows).
fetch("/corpus")
  .then(r => r.json())
  .then(d => {
    if (!d || d.total == null) return;
    document.getElementById("corpus-count").textContent =
      `${d.total} family-office record${d.total === 1 ? "" : "s"}`;
    const parts = [];
    if (d.mfo) parts.push(`${d.mfo} ${d.mfo === 1 ? "is a confirmed multi-family office" : "are confirmed multi-family offices"}`);
    if (d.sfo) parts.push(`${d.sfo} ${d.sfo === 1 ? "is a confirmed single-family office" : "are confirmed single-family offices"}`);
    if (d.unconfirmed) parts.push(`${d.unconfirmed} ${d.unconfirmed === 1 ? "has" : "have"} unconfirmed type`);
    document.getElementById("type-breakdown").textContent =
      parts.length ? "; " + parts.join(", ") : "";
  }).catch(() => {});
