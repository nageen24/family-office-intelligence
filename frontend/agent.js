// Agent page: call /agent (bounded worker + independent release authority),
// render the 5-state product language with structured output + confidence.

const goalEl = document.getElementById("goal");
const agentBtn = document.getElementById("agent");
const answerEl = document.getElementById("answer");

const STATE_COPY = {
  answered:      "Answer released after an independent review.",
  nothing_found: "Nothing in the corpus matches that.",
  partial:       "Partial answer — see the scope note.",
  declined:      "The evidence didn't support a confident answer, so the agent declined rather than guess.",
  error:         "Momentarily unavailable — this is on our side, not your question.",
};

function cardClass(state) {
  if (state === "answered") return "answered";
  if (state === "error") return "error";
  if (state === "nothing_found" || state === "declined") return "declined";
  return "no_match";
}

function renderAgent(d) {
  const el = document.createElement("div");
  el.className = "card " + cardClass(d.state);

  const p = document.createElement("p");
  p.className = "text";
  p.style.whiteSpace = "pre-wrap";
  p.textContent = d.message || STATE_COPY[d.state] || "";
  el.appendChild(p);

  const out = d.output;

  // Structured shortlist: one row per firm with an explicit confidence pill.
  if (d.state === "answered" && out && Array.isArray(out.shortlist) && out.shortlist.length) {
    const list = document.createElement("div");
    list.className = "shortlist";
    out.shortlist.forEach(s => {
      const row = document.createElement("div");
      row.className = "srow";
      const name = document.createElement("span");
      name.className = "sfirm";
      name.textContent = s.firm || "—";
      const conf = document.createElement("span");
      const c = (s.confidence || "?").toLowerCase();
      conf.className = "conf conf-" + (["high", "medium", "low"].includes(c) ? c : "unknown");
      conf.textContent = "confidence: " + (s.confidence || "?");
      row.appendChild(name);
      row.appendChild(conf);
      if (s.why) {
        const why = document.createElement("span");
        why.className = "swhy";
        why.textContent = s.why;
        row.appendChild(why);
      }
      list.appendChild(row);
    });
    el.appendChild(list);
  } else if (d.state === "answered" && out && out.answer) {
    // A direct (e.g. count) answer with no shortlist.
    const ans = document.createElement("p");
    ans.className = "text";
    ans.textContent = out.answer;
    el.appendChild(ans);
  }

  const meta = document.createElement("div");
  meta.className = "meta";
  const scope = document.createElement("span");
  scope.className = "based";
  scope.textContent = d.scope_line || "";
  meta.appendChild(scope);
  const badge = document.createElement("span");
  badge.className = "badge";
  badge.textContent = d.state === "answered" ? "✓ released by a separate authority" : "state: " + d.state;
  meta.appendChild(badge);
  el.appendChild(meta);

  answerEl.replaceChildren(el);
}

async function runAgent(goal) {
  const g = (goal || "").trim();
  if (!g) {
    answerEl.replaceChildren(Object.assign(document.createElement("div"), {
      className: "card empty", textContent: "Type a research goal for the agent, then press Run agent.",
    }));
    goalEl.focus();
    return;
  }
  agentBtn.disabled = true; goalEl.disabled = true;
  agentBtn.textContent = "Researching…";
  try {
    const r = await fetch("/agent", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal: g }),
    });
    renderAgent(await r.json());
  } catch (e) {
    renderAgent({ state: "error", scope_line: "" });
  } finally {
    agentBtn.disabled = false; goalEl.disabled = false;
    agentBtn.textContent = "Run agent";
  }
}

agentBtn.addEventListener("click", () => runAgent(goalEl.value));
goalEl.addEventListener("keydown", e => { if (e.key === "Enter") runAgent(goalEl.value); });
document.getElementById("goal-examples").addEventListener("click", e => {
  if (e.target.classList.contains("chip")) { goalEl.value = e.target.textContent; runAgent(goalEl.value); }
});

// honest, dynamic corpus size for the agent-page header (no hard-coded number).
fetch("/corpus")
  .then(r => r.json())
  .then(d => {
    if (!d || d.total == null) return;
    const el = document.getElementById("corpus-count");
    if (el) el.textContent = `${d.total} family-office record${d.total === 1 ? "" : "s"}`;
  }).catch(() => {});
