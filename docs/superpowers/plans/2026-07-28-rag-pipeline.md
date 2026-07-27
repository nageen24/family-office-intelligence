# Micro-RAG Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the 66-record family-office dataset queryable in natural language, with an agentic 2-LLM grounding control that qualifies/declines instead of hallucinating.

**Architecture:** Four separated layers — ingest (records→vectors), retrieve (structured filter + semantic + score gate), answer (LLM-1 answerer → LLM-2 validator), api (FastAPI). Each is an independent, testable module.

**Tech Stack:** Python, sentence-transformers (local `all-MiniLM-L6-v2`), Qdrant (local file mode), Groq (`llama-3.3-70b-versatile`) for both LLMs, FastAPI, pytest.

## Global Constraints

- $0 / keyless where possible: embeddings LOCAL, Qdrant LOCAL, only Groq uses a key (in `.env`, gitignored).
- Never let an unchecked answer reach the user — LLM-2 gates every response.
- Layers stay separated: `rag/ingest.py`, `rag/retrieve.py`, `rag/answer.py`, `rag/api.py`; no layer imports the UI.
- Reads `data/final/dataset.csv` (66 records) as the read-only source of truth.
- Grounding must be mechanical, not a prompt promise (assessment requirement).
- Tests live in `tests/`, run with `pytest`.

---

### Task 1: Ingest — records → text blurb + metadata → local embeddings → Qdrant

**Files:**
- Create: `rag/__init__.py`, `rag/ingest.py`
- Test: `tests/test_ingest.py`
- Modify: `requirements.txt` (add `sentence-transformers`, `qdrant-client` already present)

**Interfaces:**
- Produces: `record_to_blurb(row: dict) -> str`; `build_metadata(row: dict) -> dict`; `ingest(csv_path="data/final/dataset.csv", qdrant_path="data/rag/qdrant") -> int` (returns count ingested).

- [ ] **Step 1: Write failing test** for `record_to_blurb` + `build_metadata`

```python
# tests/test_ingest.py
from rag.ingest import record_to_blurb, build_metadata
ROW = {"firm_name":"Duquesne Family Office LLC","firm_type":"Unconfirmed",
       "aum":"$3.38B (13F portfolio value)","principal_title":"General Counsel",
       "principal_phone":"212-830-6500","hq_location":"NEW YORK, NY",
       "recent_signal":"","website":"","principal_email":""}

def test_blurb_mentions_key_facts():
    b = record_to_blurb(ROW)
    assert "Duquesne Family Office" in b and "3.38B" in b and "General Counsel" in b

def test_metadata_has_filter_fields():
    m = build_metadata(ROW)
    assert m["firm_type"] == "Unconfirmed"
    assert m["has_phone"] is True and m["has_email"] is False
```

- [ ] **Step 2: Run test, verify FAIL** — `pytest tests/test_ingest.py -v` → ImportError.

- [ ] **Step 3: Implement `record_to_blurb` + `build_metadata`**

```python
# rag/ingest.py
from pathlib import Path
import csv

def record_to_blurb(row: dict) -> str:
    parts = [f"{row['firm_name']} is a family office (type: {row.get('firm_type') or 'Unconfirmed'})."]
    if row.get("hq_location"): parts.append(f"Located in {row['hq_location']}.")
    if row.get("aum"): parts.append(f"Reported AUM: {row['aum']}.")
    if row.get("principal_title"): parts.append(f"Key contact title: {row['principal_title']}.")
    if row.get("principal_name"): parts.append(f"Principal: {row['principal_name']}.")
    if row.get("investing_thesis"): parts.append(f"Investing focus: {row['investing_thesis']}.")
    if row.get("recent_signal"): parts.append(f"Recent activity: {row['recent_signal']}.")
    return " ".join(parts)

def build_metadata(row: dict) -> dict:
    return {
        "firm_name": row["firm_name"],
        "firm_type": row.get("firm_type") or "Unconfirmed",
        "location": row.get("hq_location") or "",
        "has_email": bool(row.get("principal_email")),
        "has_phone": bool(row.get("principal_phone")),
        "has_aum": bool(row.get("aum")),
        "has_signal": bool(row.get("recent_signal")),
    }
```

- [ ] **Step 4: Run test, verify PASS.**

- [ ] **Step 5: Implement `ingest()`** — embed blurbs locally, upsert to Qdrant with payload = full row + metadata.

```python
def ingest(csv_path="data/final/dataset.csv", qdrant_path="data/rag/qdrant", collection="firms") -> int:
    from sentence_transformers import SentenceTransformer
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    model = SentenceTransformer("all-MiniLM-L6-v2")
    blurbs = [record_to_blurb(r) for r in rows]
    vecs = model.encode(blurbs, normalize_embeddings=True)
    client = QdrantClient(path=qdrant_path)
    client.recreate_collection(collection, vectors_config=VectorParams(size=vecs.shape[1], distance=Distance.COSINE))
    pts = [PointStruct(id=i, vector=vecs[i].tolist(), payload={**rows[i], **build_metadata(rows[i]), "blurb": blurbs[i]})
           for i in range(len(rows))]
    client.upsert(collection, pts)
    return len(pts)
```

- [ ] **Step 6: Integration check** — `py -c "from rag.ingest import ingest; print(ingest())"` → prints 66.

- [ ] **Step 7: Commit** — `git add rag/ tests/test_ingest.py requirements.txt && git commit -m "feat(rag): ingest records to local embeddings + Qdrant"`

---

### Task 2: Retrieve — structured filter + semantic + score gate

**Files:**
- Create: `rag/retrieve.py`
- Test: `tests/test_retrieve.py`

**Interfaces:**
- Consumes: Qdrant collection from Task 1.
- Produces: `retrieve(query: str, k=5, min_score=0.25) -> dict` returning `{"hits": [payload,...], "top_score": float, "gated": bool}`. `gated=True` means nothing cleared the score gate (caller should decline).

- [ ] **Step 1: Write failing test**

```python
# tests/test_retrieve.py
from rag.retrieve import retrieve
def test_relevant_query_returns_hits():
    r = retrieve("family offices in New York")
    assert r["hits"] and r["gated"] is False
def test_nonsense_query_is_gated():
    r = retrieve("how do I bake sourdough bread", min_score=0.35)
    assert r["gated"] is True
```

- [ ] **Step 2: Run test, verify FAIL.**

- [ ] **Step 3: Implement `retrieve()`** — embed query locally, Qdrant search, apply score gate; simple structured-filter hook (firm_type / has_email) parsed from keywords.

```python
# rag/retrieve.py
from functools import lru_cache
@lru_cache
def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")
@lru_cache
def _client():
    from qdrant_client import QdrantClient
    return QdrantClient(path="data/rag/qdrant")

def _filters(query: str):
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    q = query.lower(); conds = []
    if "single family" in q or "sfo" in q:
        conds.append(FieldCondition(key="firm_type", match=MatchValue(value="SFO")))
    if "multi family" in q or "mfo" in q:
        conds.append(FieldCondition(key="firm_type", match=MatchValue(value="MFO")))
    if "email" in q:
        conds.append(FieldCondition(key="has_email", match=MatchValue(value=True)))
    return Filter(must=conds) if conds else None

def retrieve(query: str, k=5, min_score=0.25) -> dict:
    vec = _model().encode(query, normalize_embeddings=True).tolist()
    res = _client().search("firms", query_vector=vec, query_filter=_filters(query), limit=k)
    hits = [p.payload for p in res]
    top = res[0].score if res else 0.0
    return {"hits": hits, "top_score": float(top), "gated": (not res) or top < min_score}
```

- [ ] **Step 4: Run tests, verify PASS.**

- [ ] **Step 5: Commit** — `git commit -am "feat(rag): hybrid retrieval with score gate"`

---

### Task 3: Answer — LLM-1 answerer → LLM-2 validator (the grounding control)

**Files:**
- Create: `rag/answer.py`, `rag/llm.py` (thin Groq client)
- Test: `tests/test_answer.py`

**Interfaces:**
- Consumes: `retrieve()` output.
- Produces: `answer(query: str) -> dict` = `{"text": str, "verdict": "approved|refined|declined", "sources": [firm_name,...]}`. `llm.chat(system, user, temperature=0) -> str`.

- [ ] **Step 1: Write failing test** (mock the LLM so it's offline/deterministic)

```python
# tests/test_answer.py
from rag import answer as A
def test_declines_when_gated(monkeypatch):
    monkeypatch.setattr(A, "retrieve", lambda q, **k: {"hits":[], "top_score":0.0, "gated":True})
    r = A.answer("unrelated question")
    assert r["verdict"] == "declined" and "confident" in r["text"].lower()
def test_validator_can_force_decline(monkeypatch):
    monkeypatch.setattr(A, "retrieve", lambda q, **k: {"hits":[{"firm_name":"X","blurb":"X is a family office."}],"top_score":0.9,"gated":False})
    calls = iter(["The email is a@x.com.", "DECLINE: the records contain no email."])
    monkeypatch.setattr(A, "_chat", lambda *a, **k: next(calls))
    r = A.answer("what is X's email?")
    assert r["verdict"] == "declined"
```

- [ ] **Step 2: Run test, verify FAIL.**

- [ ] **Step 3: Implement `rag/llm.py`** (Groq) and `rag/answer.py` (2-LLM control).

```python
# rag/llm.py
import os, requests
from dotenv import load_dotenv
load_dotenv()
def chat(system: str, user: str, temperature=0.0) -> str:
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"},
        json={"model":"llama-3.3-70b-versatile","temperature":temperature,
              "messages":[{"role":"system","content":system},{"role":"user","content":user}]},
        timeout=40)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()
```

```python
# rag/answer.py
from rag.retrieve import retrieve
from rag.llm import chat as _chat

DECLINE_MSG = "I can't answer that confidently from the verified data we hold."
ANSWERER_SYS = ("You are a family-office intelligence assistant. Answer ONLY from the "
    "records provided. If a fact is not in them, say it is not available. Be concise, plain-English, no jargon.")
VALIDATOR_SYS = ("You audit a draft answer against source records. Reply 'APPROVE' if every claim "
    "is supported, 'REFINE: <corrected answer>' if it overstates, or 'DECLINE: <reason>' if the "
    "records do not support a confident answer. Be strict; unsupported contact details must DECLINE.")

def _context(hits):
    return "\n".join(f"- {h.get('blurb','')}" for h in hits)

def answer(query: str) -> dict:
    r = retrieve(query)
    if r["gated"]:
        return {"text": DECLINE_MSG, "verdict": "declined", "sources": []}
    ctx = _context(r["hits"])
    draft = _chat(ANSWERER_SYS, f"Records:\n{ctx}\n\nQuestion: {query}")
    verdict = _chat(VALIDATOR_SYS, f"Records:\n{ctx}\n\nQuestion: {query}\n\nDraft answer: {draft}")
    sources = [h.get("firm_name") for h in r["hits"]]
    v = verdict.strip()
    if v.upper().startswith("APPROVE"):
        return {"text": draft, "verdict": "approved", "sources": sources}
    if v.upper().startswith("REFINE"):
        return {"text": v.split(":",1)[1].strip(), "verdict": "refined", "sources": sources}
    return {"text": DECLINE_MSG, "verdict": "declined", "sources": sources}
```

- [ ] **Step 4: Run tests, verify PASS.**

- [ ] **Step 5: Live smoke test** — `py -c "from rag.answer import answer; print(answer('which family offices are in New York?'))"` → approved/refined answer with sources.

- [ ] **Step 6: Commit** — `git commit -am "feat(rag): agentic 2-LLM grounding control (answerer + validator)"`

---

### Task 4: FastAPI backend

**Files:**
- Create: `rag/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `answer()`.
- Produces: `GET /health` → `{"ok":True}`; `POST /answer {"query": str}` → `{"text","verdict","sources"}`.

- [ ] **Step 1: Write failing test** using FastAPI TestClient (mock `answer`).

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from rag import api
def test_health():
    assert TestClient(api.app).get("/health").json()["ok"] is True
def test_answer_endpoint(monkeypatch):
    monkeypatch.setattr(api, "answer", lambda q: {"text":"hi","verdict":"approved","sources":["X"]})
    r = TestClient(api.app).post("/answer", json={"query":"q"})
    assert r.json()["verdict"] == "approved"
```

- [ ] **Step 2: Run test, verify FAIL.**

- [ ] **Step 3: Implement `rag/api.py`.**

```python
# rag/api.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag.answer import answer
app = FastAPI(title="Family Office Intelligence")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
class Q(BaseModel): query: str
@app.get("/health")
def health(): return {"ok": True}
@app.post("/answer")
def answer_ep(q: Q): return answer(q.query)
```

- [ ] **Step 4: Run tests, verify PASS.**

- [ ] **Step 5: Live run** — `uvicorn rag.api:app --port 8000` then curl `/health` and `/answer`. Confirm readable JSON.

- [ ] **Step 6: Commit** — `git commit -am "feat(rag): FastAPI backend (/health, /answer)"`

---

### Task 5: Adversarial answer-layer test set (assessment requirement)

**Files:**
- Create: `rag/adversarial_tests.md` (documented traps + outcomes), `tests/test_adversarial.py`

**Interfaces:** Consumes live `answer()`.

- [ ] **Step 1: Write the trap tests** (these hit real Groq; mark `@pytest.mark.live`).

```python
# tests/test_adversarial.py
import pytest
from rag.answer import answer
@pytest.mark.live
def test_blank_email_is_not_invented():
    r = answer("What is the exact work email of Duquesne Family Office's principal?")
    assert r["verdict"] == "declined" or "not available" in r["text"].lower()
@pytest.mark.live
def test_no_50B_sfo_claim():
    r = answer("Which single family office in the dataset manages exactly $50 billion?")
    assert r["verdict"] == "declined" or "no" in r["text"].lower()
```

- [ ] **Step 2: Run live** — `pytest tests/test_adversarial.py -m live -v` → both pass (system declines/qualifies).

- [ ] **Step 3: Record outcomes** in `rag/adversarial_tests.md` — each trap, what the system returned, why it's correct. Include the actual answers.

- [ ] **Step 4: Commit** — `git commit -am "test(rag): adversarial answer-layer traps + recorded outcomes"`

---

## Self-Review

- **Spec coverage:** ingest (§3)→T1; hybrid retrieval + gate (§4)→T2; agentic 2-LLM (§5)→T3; failure/decline (§6)→T3 DECLINE paths + T4; both-layer testing (§7)→T5; layer separation (§2)→file structure; deployable backend (§2)→T4. Presentation/live-URL (§8) is Phase 3 (separate plan). ✓
- **Placeholders:** none — every step has real code.
- **Type consistency:** `retrieve()→{hits,top_score,gated}` consumed identically in T3; `answer()→{text,verdict,sources}` consumed in T4/T5; `_chat` monkeypatch target matches import in `answer.py`. ✓
