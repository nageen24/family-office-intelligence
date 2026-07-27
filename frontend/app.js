// Customer-facing logic: call /answer, render each status as its own readable card.
// Speaks the customer's language — never shows field names, JSON, or errors.

const qEl = document.getElementById("q");
const askBtn = document.getElementById("ask");
const answerEl = document.getElementById("answer");

const COPY = {
  empty:    "Type a question to begin — try one of the examples above.",
  no_match: "No family office in our data matches that. Try broader terms, or ask about type, location, AUM, or recent activity.",
  error:    "Momentarily unavailable — this is on our side, not your question. Please try again in a moment.",
};

function card(status, text, sources) {
  const el = document.createElement("div");
  el.className = "card " + status;
  const p = document.createElement("p");
  p.className = "text";
  p.textContent = text;
  el.appendChild(p);

  // value cues only on a real answer
  if (status === "answered") {
    const meta = document.createElement("div");
    meta.className = "meta";
    const n = (sources || []).length;
    const based = document.createElement("span");
    based.className = "based";
    based.textContent = n ? `Top ${n} match${n > 1 ? "es" : ""} for this question:` : "";
    meta.appendChild(based);
    (sources || []).forEach(s => {
      const c = document.createElement("span");
      c.className = "srcchip";
      c.textContent = s;
      meta.appendChild(c);
    });
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = "✓ checked by a second AI";
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
    card(status, text, d.sources);
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
