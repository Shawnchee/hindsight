# PRD: Exploit-Aware Smart Contract Triage — **Hindsight**

| Field | Value |
|---|---|
| Status | Draft v0.3 — revised after stress test + external audit |
| Name | **Hindsight** (package and repo: `hindsight-sec`). See §16 |
| v1 language | Solidity (Vyper next; Slither already supports both) |
| Owner | Shawn |
| Last updated | 2026-10-22 |
| Purpose | A tool people actually use. Open source; commercial option kept open |
| v1 chain scope | **Ethereum mainnet only** |
| Later | Other EVM chains (BSC, Base, Arbitrum…), then Solana |
| Compute | MacBook (data, eval, local inference) + Lightning AI (GPU training, when needed) |

### Changes from v0.1
- Purpose changed from "portfolio" to **usable product** → privacy, licensing, and a working CLI move to the front.
- Model input is now **code + Slither hints + similar past hacks**, not "rank Slither's list". Two scores reported separately.
- Reasoning model is **pluggable** (local model or user's own API key). Fine-tuning is **deferred**; a simple learned ranker comes first.
- Evaluation rebuilt: per-finding adjudication, **frozen point-in-time retrieval**, three chronological partitions with a sealed test set, corrected metric names.
- Dataset size is set by **measured review time**, not a fixed 300.
- Sources restricted to ones whose terms allow this use. No scraping of X or Solodit.
- Real numbers from DeFiHackLabs added (§3); unmeasured claims qualified.

---

## 1. Summary

Hindsight scans a Solidity project and returns a short, ranked list of the issues most likely to matter, each backed by evidence and by the **real historical exploits** it resembles.

It combines three inputs:
1. The project's **source code**.
2. **Slither** findings, used as hints (not as a limit — Hindsight may flag things Slither missed).
3. **Retrieved precedent** from a daily-updated database of real exploits with reproducible PoCs.

**Value prop:** *"Slither prints 80 warnings and a frontier model gives you a confident essay. Hindsight tells you which few look like things that actually got exploited, shows you those exploits, and says what it couldn't check."*

**Tagline (README first line):** *"Runs on your machine. Your code is never uploaded unless you turn on API mode."*

What "local" means, precisely, so the claim stays true:
- **Never sent anywhere in local mode:** your source code, Slither output, code slices, embeddings of your code.
- **Downloaded (public data only):** the exploit index update, compiler binaries (`solc`), your project's own declared dependencies.
- **API mode (opt-in):** the CLI prints which code slices go to which provider before sending.
- **Honest caveat:** local mode uses a smaller model and will be less accurate than API mode. The report says which mode ran.

### Why Solidity only (v1)
- Ethereum mainnet victims in DeFiHackLabs are overwhelmingly Solidity, so that's where labeled data is.
- Slither, Etherscan verification, and Foundry PoCs all work best on Solidity.
- **Vyper is next**: Slither already supports it and Curve-style Vyper protocols matter. Needs a Vyper slice of the dataset first.
- Unverified (bytecode-only) contracts are out of scope: no source, nothing to triage.
- Solana (Rust) is a separate parser and dataset (§8.4).

---

## 2. Problem

1. **Static analyzers are noisy.** Slither/Aderyn produce many findings per codebase; triage takes real reviewer time.
2. **Exploit knowledge is scattered and fresh knowledge is missing from LLMs.** Root-cause analyses live across DeFiHackLabs, post-mortems, security-firm blogs. Frontier models stop at a training cutoff and don't reliably cite real precedent.
3. **LLM reviews aren't verified.** Models read code; they don't compile it, run analyzers, or replay exploits — and they rarely say what they couldn't determine.

### What Hindsight covers that a frontier model alone doesn't

| Gap in a bare frontier model | Hindsight's answer |
|---|---|
| Doesn't know exploits after its cutoff | Daily-updated exploit DB, retrieved at scan time |
| Doesn't cite real incidents reliably | Every flag links to concrete incidents + PoCs |
| Can't run tools | Pipeline compiles, runs Slither, (later) replays on a fork |
| Over-flags | Ranker calibrated on adjudicated real outcomes |
| Sends your code to a third party | Local mode is the default |

**The differentiator is the system (data + tools + verification), not the model weights.** The reasoning model is swappable.

### Competition (checked 2026-10-22, not exhaustive)
- **Slither-MCP (Trail of Bits)** lets Claude Code / Cursor call Slither directly. That is roughly our baseline **B3 without the exploit database** — and anyone can set it up today. **This is the bar.** Hindsight only wins if precedent retrieval + the benchmark add measurable value on top.
- **LLM-over-Slither pipelines** (e.g. a polymarket-developers repo, several agent "skills") already explain and triage Slither findings, some with local models via Ollama.
- Reported in a 2026 guide: LLM auditing raises recall but false-positive rates on real DeFi code can exceed 97%. Calibration is an open problem, which is our opening.

**Implication:** "LLM + Slither, local" is not a differentiator on its own. The defensible parts are (1) the curated, reviewed, point-in-time exploit dataset, (2) the public benchmark, (3) evidence-backed, calibrated output. Ship the dataset and benchmark publicly even if the tool loses.

### Will people use it? (adoption hypotheses — to be tested, not assumed)
| Who | Why they might | Why they might not |
|---|---|---|
| Audit-contest participants | Free, fast first pass; "has this been exploited before?" | Many already have their own scripts + Claude |
| Small teams before an audit | Cheaper than nothing; private | Will just paste code into a chat model |
| Auditing firms | Private, local, precedent citations | High bar; need proven precision |
| Researchers | The dataset + benchmark | Not the CLI |

**Adoption gate (M2):** 10 people outside the project run it on a real repo and give feedback. If fewer than 3 say they'd run it again, revisit positioning before M3.

---

## 3. Facts the plan is built on (measured 2026-10-22)

From a read-only clone of DeFiHackLabs (Apache-2.0) and the DeFiLlama hacks endpoint:

| Fact | Value | Implication |
|---|---|---|
| DeFiHackLabs PoCs | ~932 total; 338 in last 24 mo; 160 in last 12 mo | Volume is fine; **review time** is the bottleneck |
| Chain mix, last 12 mo | Ethereum 62, BSC 52, unresolved 1 (M0 catalog parser, which resolves RPC constants; first pass said 58/44/22) | Ethereum is the best single-chain start |
| Ethereum mainnet incidents, all time | 357 of 899 README entries (DHL commit `23c7bd8`) | Upper bound on the v1 seed set before the funnel |
| Funnel, Ethereum, 24 mo, Sourcify only (127 in scope) | Victim address found 80% → source recovered 61% → compiles 59% → Slither runs 58% → **not a proxy 42%** | Proxies (21 of 77 recovered) are the biggest fixable loss: resolving the implementation needs an Etherscan key + archive RPC. An Etherscan key is estimated to raise source recovery to ~76% (not measured) |
| **Slither coverage: two blind LLM reviews (Opus 5.5 proposals + Fable 5.1 review), not yet human-verified** | **Strict: 3 of 27** (11%). These are in-scope incidents where Slither ran on the victim and a finding *describes* the exploited weakness: Revest and Rari (reentrancy), Anyswap (permit). **Loose: 21 of 27** (78%): a finding sits in a causal function but describes something else. Both models agreed on every "which finding explains it" call (38/38) | Strict is far below the ~30% line in §5, so sorting Slither's output can't be the product. Slither is still useful as a **location hint**: it lands in the right function 78% of the time, just for the wrong reason. Caveat: the two models are from the same family, so their errors may be correlated |
| **B2: frontier model, code only** (Sonnet 5.5, blind case IDs, no PoC, labels or web; `m0/b2/summary.md`) | **Hit@5: 19 of 27 (70%)**, Hit@1 14 of 27 (52%). Before 2026-07: 18 of 24 (75%). From 2026-07 on (likely post-cutoff): **1 of 3**. B0 (Slither's top-5 functions): 10 of 27 (37%) | A frontier model alone already finds the buggy function in most known hacks, which is about twice Slither. Inflation is likely: the model named one case "Audius-style" from memory, and the labels come from the same model family. **6 of the 8 misses are data gaps, not reasoning failures:** only the proxy was recovered, the facet was missing, or the wrong contract was supplied (EFVault, Unizen, Beanstalk, GoodDollar, Audius, BiFi). n=3 post-cutoff can't support any conclusion |
| **B2 v2: post-cutoff exploits + clean contracts, mixed blind** (`m0/b2/v2/summary.md`) | 23 Ethereum exploits from 2026-07 on, mixed with 12 famous audited clean contracts. The prompt told the model some cases are clean. **Hit@5 17 of 22 (77%)**, Hit@1 9 of 22 (41%). **But the model said "exploitable bug" (medium/high) on only 2 of 23 real exploits (9%).** Clean false positives: 0 of 12. Slither's strict coverage on this set: 1 of 23 | **This is the gap.** A frontier model's top-5 usually *contains* the buggy function, but it doesn't *recognize* it as exploitable. It calls nearly everything "probably fine". Hindsight's job is to turn "this function is in the list" into "this function is exploitable, like incidents X and Y". That's what precedent retrieval and calibration are for. Most Hit@5 misses again had only the proxy or diamond source (StrongBlock, Arrakis, Reddio, SecuredFi, RsETH). Caveats: the "some are clean" prompt probably made the model conservative, the clean set is famous (that flatters the FP rate), the labels are LLM labels, and n is small |
| Post-cutoff label agreement (blind Opus 5.5 vs blind Fable 5.1, 30 incidents) | Victim overlap 30/30. Causal-function overlap 25/26. Root-cause overlap 28/28 (exact match 22/28). "Which Slither finding explains it" 28/28. In-scope 28/30: TermFinance and Enjin, where Opus excluded both partly *because source is missing*, which is the wrong criterion | Post-cutoff ground truth is consistent across two models. Both are Claude-family, so a human check is still needed before the sealed test set |
| Victim source and Slither on the sample | Slither ran on the victim for 27 of 39 in-scope incidents. 12 have no usable source (mostly not on Sourcify, or only the proxy recovered) | An Etherscan key and proxy resolution are the next data fixes |
| Label quality | Opus and Fable root-cause labels overlap on 36 of 38. They disagree exactly on 13, mostly where Fable adds `input_validation` as a second label. Real conflicts: Conic, Peapods. Scope conflicts: Miso, ActivePool. The DHL label is wrong in 6 of 39 (15%). 35 of 39 have more than one causal location | The multi-label, multi-location schema is justified. `input_validation` overlaps with other classes, so tighten its definition at the taxonomy revision |
| Slither noise per contract | Median 47 findings per compilation unit, 21 in the target file. Impact medians: High 2, Medium 3, Low 7, Info 23.5 | Confirms the triage problem. Even "High" alone gives ~2 per contract |
| DHL coverage vs DeFiLlama (Ethereum, code-level, 24 mo) | DHL has 65 of 134 (49%); ~67 missed; in the slow months it caught only 6 of 20 (30%). DeFiLlama in turn lacks 54 DHL entries | News discovery is required, not optional. Neither source is complete |
| Labels | 898/899 entries labeled, but free-text, inconsistent; recent ones are prose | Needs normalisation to our taxonomy |
| Buggy function obvious? | ~14/20 sampled recent PoCs; ~6 multi-step / multi-contract | Must support multi-location root causes |
| PoC headers | Contain written root-cause analyses | **Must strip before eval** or the answer leaks |
| Old code exploited recently | Many 2026 incidents hit dormant 2020–21 contracts | Exploit date ≠ code date → contamination risk |
| Off-chain causes | <2% in DeFiHackLabs; ~27% of DeFiLlama's 1,314 incidents | DeFiHackLabs is biased to fork-replayable code bugs |
| DeFiHackLabs update gaps | 1–6 new entries/month from 2025-09 to 2026-02, then 34 in 2026-09 | **Relying on one repo leaves months-long holes** → need independent news discovery (§7.1) |

These are from one sampling pass; M0 re-measures them for Ethereum mainnet specifically.

---

## 4. Goals and non-goals

### Goals
- **G1** — Structured, deduplicated, daily-updated Ethereum mainnet exploit dataset with recovered source and reviewed labels.
- **G2** — A working CLI early (M2), so failures can be inspected on real projects.
- **G3** — A reproducible, leak-free benchmark (§9).
- **G4** — Beat a **properly configured** Slither baseline and a bare frontier model on the post-cutoff test set (§5).
- **G5** — Daily ingestion automated; retraining automated only after it has been shown to help.

### Non-goals
- **Not** an exploit generator. No working attack transactions against live contracts.
- **Not** a trading / MEV / farming bot. Permanently out of scope.
- **Not** an audit. Output is triage assistance and says so.
- **Not** pretraining or training from scratch.
- **Not** fine-tuning an LLM in v1 (deferred to M5, conditional). Small models **are** trained in v1 (§7.9).
- **Not** real-time mempool monitoring.
- **Not** multi-chain in v1. Schema supports it (§8.4).

---

## 5. Success metrics

### Metric definitions (all reported per model version)

| Metric | What it measures |
|---|---|
| **Incident Hit@5** *(north star)* | Fraction of test incidents where an exploit-relevant issue appears in Hindsight's top 5. After D15, an "issue" means a ranked suspicious location, whether or not Slither flagged it |
| Finding Precision@5 | Fraction of the top 5 independently judged `confirmed_valid` |
| Root-cause Recall@5 | Fraction of labeled causal locations recovered in the top 5 |
| Valid-finding retention | Fraction of valid findings not buried below the fold after re-ranking |
| Beyond-Slither rate | Fraction of incidents where the relevant issue was found by Hindsight but **not** flagged by Slither |
| Slither coverage | Fraction of incidents where Slither flags the causal weakness at all (sets the ceiling for pure triage) |
| Review effort | Findings a reviewer must read before reaching the relevant one |
| Scan cost / latency | End-to-end: retrieval, context assembly, retries, inference |
| Abstention rate | Fraction of scans reported as partial or failed (must be reported, not hidden) |

Uncertainty is reported **per incident / exploit family** (bootstrap CIs), never treating functions as independent.

### Baselines (every report)
- **B0** Slither, practical config: severity + confidence filtering, dedup, sensible detector set.
- **B1** Retrieval-only (similarity to past exploits).
- **B2** Frontier LLM, code only.
- **B3** Frontier LLM + Slither output + frozen retrieval.
- **B4** Learned ranker (detector metadata + retrieval scores; e.g. gradient boosting).
- **Hindsight** = best configuration of the above pipeline with the chosen reasoning model.

### Targets
Set **after M0** from measured Slither coverage. Placeholder intent:
- Beat B0 on Incident Hit@5 with Valid-finding retention ≥ 90%.
- Beat B2 on post-cutoff incidents (that's the freshness claim).
- Local mode within a pre-declared margin of BYO-API mode.

### Kill / pivot criteria
- **M0:** Slither coverage < ~30% *and* B2 can't localize either → triage product has a low ceiling; reconsider scope before M1.
- **M3:** Hindsight does not beat B2 on post-cutoff incidents → the freshness/precedent claim is false; ship the dataset + retrieval as the product.
- **M5:** fine-tuned model does not beat B4 + best API model by a pre-declared margin → don't ship it.

---

## 6. Milestones

| Milestone | Deliverable | Exit criteria |
|---|---|---|
| **M0 — Spike** (1–2 wks) | 30–50 Ethereum incidents taken through the full funnel by hand | Measured: funnel yield, review minutes per incident (median + worst), Slither coverage of the causal weakness. Targets in §5 set. Go/no-go |
| **M1 — Dataset** | Ingestion, enrichment, review CLI, DB | Size = available review hours ÷ measured minutes per incident. Daily cron green 7 days. Eval set fully reviewed |
| **M2 — CLI + baselines** | `sentinel scan` working end to end (API mode); B0–B3 numbers | Run on 3 real open-source repos; failure log written |
| **M3 — Benchmark v1** | Frozen-retrieval eval harness, three partitions, sealed test | Reproducible report committed; kill criterion checked |
| **M4 — Ranker + local mode** | B4 learned ranker; local quantized model option | Local vs API margin measured |
| **M5 — Fine-tune (conditional)** | LoRA on Lightning AI only if M4 shows a gap worth closing | Beats B4 + API by declared margin on validation, confirmed once on sealed test |
| **M6 — Automation** | Gated retraining workflow | One full retrain → validate → promote/reject cycle |
| **Later** | Other EVM chains; Solana | See §8.4 |

---

## 7. Functional requirements

### 7.1 Data sources (v1)

| Source | Use | Terms (checked 2026-10-22) | Decision |
|---|---|---|---|
| **DeFiHackLabs** | Incidents, PoCs, labels | Apache-2.0 | ✅ Primary. Keep LICENSE/NOTICE attribution |
| **Etherscan V2 API** | Verified source, ABI | Free tier covers source endpoints | ✅ With rate limiting |
| **Sourcify** | Source fallback | Open | ✅ |
| **Ethereum archive RPC** | Historical state, proxy implementation at exploit block | Provider-dependent | ✅ Budget for it (§11) |
| **DeFiLlama hacks** | Discovery + `first_seen` dates | Terms grant a **personal, non-commercial** licence and prohibit copying; free endpoint is undocumented | ⚠️ Discovery signal only; don't redistribute; revisit before any commercial release |
| **Code4rena / Sherlock report repos** | Extra labeled findings | Repos carry **no license** (all rights reserved by default) | ❌ Not in v1. Link-only references at most |
| **Solodit** | Audit findings | General T&C restrict copying | ❌ Not in v1 |
| **Serper (Google Search API) / Google News RSS** | **Discovery**: find new incidents fast, find post-mortem links, set `first_seen_at` | Paid API / public feed | ✅ Discovery only. Store URL + date + our own summary |
| **X / Twitter** | Earliest alerts (security accounts post within minutes) | ToS forbid scraping; **official API is paid** | ⚠️ Official API only, discovery only, M1+ if budget allows. No scraping |
| **Security-firm blogs / post-mortems (RSS)** | Root-cause write-ups, `published_at` | Per site | ✅ Store link + our own summary, not full text, unless licence allows |

**News is for discovery, not training text.** A tweet or article tells us *that* a hack happened and *where to look*. It doesn't contain the vulnerable code. The training example is built from: victim address (from news/PoC) → verified source (Etherscan) → root cause location (post-mortem + review). Early tweets are often wrong about root cause, so news-derived labels always start as `proposed`.

**Backfill:** the same discovery pipeline runs over past years (Serper date-bounded queries) to find incidents DeFiHackLabs never added, especially during its gaps.

| ID | Requirement |
|---|---|
| ING-1 | Pull DeFiHackLabs daily; detect new/changed entries by commit SHA. Filter to Ethereum mainnet for v1. |
| ING-2 | Store every raw document immutably: `source`, `url`, `fetched_at`, `published_at`, `content_hash`, version. |
| ING-3 | Idempotent runs; no duplicates. |
| ING-4 | API/git first; respect rate limits and each source's terms. |
| ING-5 | Failures surface via CI failure notification. |

### 7.2 Enrichment

| ID | Requirement |
|---|---|
| ENR-1 | Resolve victim addresses from PoC header. |
| ENR-2 | Fetch verified source + compiler settings + dependency versions; reconstruct a buildable project. |
| ENR-3 | Resolve proxy implementation **at the exploit block** via archive RPC. |
| ENR-4 | Record `code_deployed_at` (deployment block/time) separately from `occurred_at`. **Reject any artifact deployed after the exploit block.** It's post-patch code. Seen in M0: Audius's Governance implementation was deployed about 2,000 blocks after the exploit, and DeFiHackLabs lists it in the PoC header. In the review sample, 1 of 86 candidates with a known deploy block was affected. |
| ENR-5 | Extract PoC call path (evidence of execution, **not** proof of root cause). |
| ENR-6 | Move PoC comments and write-ups **and the DHL README label text** into a separate label-evidence field. Eval inputs never contain them. Recent README labels are full root-cause write-ups, and 48 of the 59 Ethereum PoCs from 2026 have a written analysis in the header. |
| ENR-7 | LLM proposes labels → `proposed`. |
| ENR-8 | Run pinned Slither; store findings with detector, impact, confidence, locations. |
| ENR-9 | Fork / near-duplicate clustering by code similarity → `exploit_family_id`. |
| ENR-10 | All downloaded PoCs and build scripts run in a disposable, network-restricted container with no keys or credentials. |

### 7.3 Review

What a reviewer does per incident (target time measured in M0):
1. Confirm recovered source matches the deployed bytecode.
2. Set **root cause**, **attack mechanism**, and **impact** separately (e.g. root cause = trusts manipulable spot price; mechanism = flash loan; impact = drained pool).
3. Mark causal code location(s) — one or many, or contract-level — with a role (`defect`, `entry_point`, `affected`).
4. Adjudicate Slither findings on those locations: `confirmed_valid` / `confirmed_invalid` / `unresolved`, plus `explains_exploit` yes/no, with a short rationale.

| ID | Requirement |
|---|---|
| REV-1 | Review CLI shows source, PoC, Slither output, proposed labels side by side. |
| REV-2 | All edits logged (`label_event`). |
| REV-3 | **Eval sets (validation + sealed test): 100% human-reviewed.** Training/retrieval data: LLM labels with ≥ 1-in-10 spot check; spot-check error rate reported. |
| REV-4 | Re-open when later post-mortems contradict a label. |
| REV-5 | Sample incidents across time, categories, and complexity — not only high-loss ones. |

### 7.4 Retrieval

| ID | Requirement |
|---|---|
| RET-1 | Index at function level plus contract-level summaries. |
| RET-2 | Every query takes an **as-of date**; only documents with `first_seen_at` / `published_at` before it are eligible. |
| RET-3 | In evaluation, the target incident and its whole `exploit_family_id` are excluded. |
| RET-4 | Each index build is versioned: embedding model + version, content hashes, build timestamp. |
| RET-5 | Unverified (`proposed`) records are retrievable in production but flagged; they obey RET-2/3 in eval. |
| RET-6 | Two-stage retrieval: embeddings pick the top ~50 candidates, then a **cross-encoder reranker** reorders them and keeps the top 3–5. |
| RET-7 | The reranker must be Apache-2.0 or MIT and run on a laptop. Candidates: `BAAI/bge-reranker-v2-m3`, `mixedbread-ai/mxbai-rerank-base-v2`, `Alibaba-NLP/gte-reranker-modernbert-base` (all Apache-2.0, checked 2026-10-22). **Jina rerankers v2, v3 and m0 are CC-BY-NC-4.0 → excluded**, because they block commercial use. |
| RET-8 | Code embeddings: candidates include `jinaai/jina-embeddings-v2-base-code` (Apache-2.0). Chosen by the M2 benchmark. |

### 7.5 Reasoning model

| ID | Requirement |
|---|---|
| MOD-1 | Pluggable backend: (a) local quantized open model (MLX / llama.cpp), (b) user's own API key for a frontier model. |
| MOD-2 | Input per candidate: relevant code slice + call-graph neighbours, Slither findings (if any), top-k retrieved precedents. |
| MOD-3 | Model may propose issues not in Slither's output; those are tagged `source = model`. |
| MOD-4 | Structured, validated output (schema-constrained); retries counted in cost. |
| MOD-5 | Learned ranker (B4) combines model output, detector metadata, retrieval scores. |
| MOD-6 | Fine-tuning only at M5, only if justified, on full verified training partition (never only the delta). |

### 7.6 Output (CLI: `sentinel scan <path>`)

| ID | Requirement |
|---|---|
| OUT-1 | Every scan reports one of: **complete**, **partial** (with what was missing — deps, build, source), or **failed**. |
| OUT-2 | Each issue has: review priority (`high` / `medium` / `low` / `needs_review`), evidence, missing context, and up to 3 cited precedents. |
| OUT-3 | Each precedent says **what matches** and **which exploit prerequisites are not established**. Precedent ≠ proof. |
| OUT-4 | Full finding list preserved; low-priority items collapsible, never dropped. |
| OUT-5 | Markdown / HTML / JSON export (JSON for CI use later). |
| OUT-6 | "Triage aid, not an audit" disclaimer. |

### 7.7 Privacy

| ID | Requirement |
|---|---|
| PRV-1 | **Default: nothing leaves the machine.** Local model, local copy of the retrieval index. |
| PRV-2 | API mode is opt-in, per scan, and states exactly what is sent (code slices, findings) and to whom. |
| PRV-3 | No telemetry by default. |
| PRV-4 | Remote retrieval (if ever offered) sends only the minimum needed, documented. Embeddings of user code are treated as user code. |

### 7.9 What gets trained (and what doesn't)

The pipeline is "retrieve → rerank → reason → rank". Three trained parts, from cheapest to most expensive:

| Model | What it learns | Trained on | Where | When |
|---|---|---|---|---|
| **Precedent reranker** (fine-tuned cross-encoder, ~0.3–0.6B) | Which past exploit actually matches this code. Embeddings alone only find code that *looks* similar | Reviewed (code location, matching incident) pairs + hard negatives from the same category | Lightning AI GPU (hours), runs on the Mac | M3–M4, after the baseline off-the-shelf reranker is measured |
| **Findings ranker** (gradient boosting / learning-to-rank) | Which candidate issues to show first | Detector, impact, confidence, reranker scores, model verdict, adjudication labels | Mac CPU (minutes) | M4 (baseline B4) |
| **Reasoning LLM** (LoRA) | Better judgments on exploit-like code | Reviewed incidents | Lightning AI | M5, only if the two above leave a measurable gap |

Each trained model must beat its untrained version on the **validation** partition before it ships:
- the fine-tuned reranker vs. the off-the-shelf reranker
- the findings ranker vs. Slither's own ordering

Same leak rules as §9.

### 7.8 Retraining (M6)

| ID | Requirement |
|---|---|
| RTR-1 | Trigger: **≥ 50 new verified examples AND ≥ 30 days since last train.** |
| RTR-2 | Promote using the **validation** partition only. Sealed test is touched once per milestone. |
| RTR-3 | Prospective check: new reviewed incidents are scored by the current model **before** joining training. |
| RTR-4 | Every model version traceable to dataset snapshot, index version, code commit, config, eval report. |

---

## 8. Data model

### 8.1 Core tables (Postgres + pgvector)

```sql
incident (
  id uuid pk, vm text, chain text, protocol text,
  occurred_at timestamptz, exploit_block bigint,
  first_seen_at timestamptz,            -- when we/anyone first saw it
  loss_usd numeric, attack_tx text[],
  exploit_family_id uuid,
  off_chain bool,                       -- key compromise etc.; excluded from code tasks
  taxonomy_version text,
  -- evidence states, tracked separately
  source_status  text,  -- none | explorer_verified | bytecode_matched
  build_status   text,  -- not_tried | fails | builds
  replay_status  text,  -- not_tried | fails | reproduces
  review_status  text,  -- proposed | reviewed | disputed | rejected
  violated_invariant text, summary text, evidence_links jsonb,
  created_at, updated_at
)

incident_label (incident_id fk, kind text, value text)   -- kind: root_cause | mechanism | impact (multi-label)

contract_artifact (
  id uuid pk, chain text, address text, code_deployed_at timestamptz,
  compiler_version text, compiler_settings jsonb, dependencies jsonb,
  source_files jsonb, source_hash text, bytecode_hash text
)
incident_contract (incident_id fk, artifact_id fk, role text)       -- many-to-many
proxy_link (proxy_artifact_id fk, impl_artifact_id fk, from_block bigint, to_block bigint)

code_location (
  id uuid pk, artifact_id fk, file text, start_line int, end_line int,
  function_sig text null, level text        -- function | contract | multi
)
incident_location (incident_id fk, location_id fk, causal_role text, evidence text)

analyzer_finding (
  id uuid pk, artifact_id fk, tool text, tool_version text, detector text,
  impact text, confidence text, location_id fk
)
finding_adjudication (
  finding_id fk, status text,               -- confirmed_valid | confirmed_invalid | unresolved
  explains_exploit bool, rationale text, reviewer text, evidence text, at timestamptz
)

document (
  id uuid pk, source text, url text, published_at timestamptz, fetched_at timestamptz,
  content_hash text unique, version int, licence text, content text null  -- null if licence forbids storing
)

embedding (id, location_id fk, model text, model_version text, content_hash text, vector vector(N))
index_build (id, embedding_model, built_at, as_of timestamptz, content_hashes_digest text)
label_event (id, entity, entity_id, field, old, new, actor, at)
model_version (id, backend, base_model, dataset_snapshot, index_build_id, commit, metrics jsonb, promoted bool)
```

### 8.2 Taxonomy (v0, versioned — expect one revision after M1)

Root cause, mechanism, and impact are **separate** fields.

- **Root cause:** `access_control` · `price_oracle_trust` · `rounding_precision` · `arithmetic_overflow_or_cast` · `input_validation` · `reentrancy` · `business_logic` · `signature_validation` (replay, permit, bad signature checks) · `uninitialized_or_unprotected_init` · `storage_collision` · `arbitrary_external_call` · `governance_design` · `weak_randomness` · `denial_of_service` · `other`
- v0.1 of the taxonomy, revised after the M0 catalog. Of the 210 raw Ethereum labels, 82 mapped with high confidence (covering 159 incidents). About 80 incidents carry "Business Logic Flaw" and need splitting on review.
- **Mechanism:** `flash_loan` · `price_manipulation` · `reentrant_call` · `crafted_calldata` · `governance_vote` · `donation` · `other`
- **Impact:** `funds_drained` · `tokens_minted` · `funds_frozen` · `governance_takeover` · `other`

DeFiHackLabs free-text labels are mapped into this via a reviewed lookup table.

### 8.3 Ethereum-first constraints
Every table carries `vm` / `chain`. No Ethereum-only assumptions above the enrichment layer.

### 8.4 Later chains
- **Other EVM chains:** mostly new source/RPC config; BSC has the largest historical share but source-availability rate is unmeasured.
- **Solana:** new parser (Anchor / native Rust), new categories (`missing_signer_check`, `missing_owner_check`, `account_confusion`, `pda_seed_collision`, `arbitrary_cpi`, `unchecked_math`), no DeFiHackLabs-scale PoC corpus known. Dataset size **unmeasured**; treat as a sibling project sharing retrieval, review, and eval infrastructure.

---

## 9. Evaluation methodology

1. **Three chronological partitions** by `first_seen_at`: **train** → **validation** (tuning, promotion) → **sealed test** (once per milestone). Exploit families never span partitions.
2. **Point-in-time retrieval.** Each eval scan runs with `as_of = incident.first_seen_at − ε`. Target incident + its family excluded. Applies to **all** baselines.
3. **Pinned everything.** Each report pins model, dataset snapshot, embedding model, index build, Slither version, config.
4. **Leak scrubbing.** PoC comments and write-ups never appear in inputs.
5. **Ground truth per finding**, not per function (§7.3). `unresolved` excluded from precision and **counted** in the report.
6. **Contamination.**
   - Report results split by **post–model-cutoff** vs pre-cutoff incidents.
   - Also split by `code_deployed_at` — old code exploited recently may still be memorized.
   - If a model's training cutoff isn't documented, contamination is reported as **unknown**, not "none".
7. **Coverage vs ranking.** Report Slither coverage and Hindsight's ranking **conditional on coverage**, plus beyond-Slither rate — so good ranking can't hide a low ceiling.
8. **Comparison set.** Audited, non-exploited contracts are an *unlabeled* comparison set (volume of high-priority flags), not negatives — unless specific findings are adjudicated.
9. **Small-n honesty.** With ~50 test incidents, one case moves Hit@5 by 2 points. Report CIs; don't gate on 2-point deltas.

---

## 10. Architecture

```
            ┌──────────── CI cron (daily) ─────────────┐
 Sources →  │ ingest → enrich (source, build, Slither, │ → Postgres + pgvector
            │ proxy@block, LLM label proposal)         │        │
            └──────────────────────────────────────────┘        ▼
                                                     Review CLI (human)
                                                               │
                                         versioned snapshot + index build
                                                               │
 user repo ─► sentinel scan ─► build + Slither ─► candidates ─┤
                                    retrieval (local index) ──┤
                                  reasoning model (local | BYO API)
                                                               ▼
                                learned ranker ─► report (complete | partial | failed)
```

### Tech defaults
Python · Foundry (PoC parsing, later replay) · Slither pinned · Supabase Postgres + pgvector · open embedding model run locally (chosen by M2 benchmark) · MLX / llama.cpp for local mode · Docker for sandboxed builds/replays.

### Lightning AI credits — how to spend them
**Update 2026-10-22: the budget is $15.** That covers a few GPU-hours on a small GPU; check Lightning's current per-hour prices. Spend it only on reranker fine-tuning at M3–M4. Everything else in the table below now runs on the Mac (24 GB) or uses Claude agents. The table is the original plan, kept for reference if more credit appears.

| When | Job | Why GPU |
|---|---|---|
| M0–M1 | Run a large open-weight model to propose labels for ~900 incidents | Cheaper than API at this volume; same model family as local mode |
| M1–M2 | Compute embeddings for the full index | Batch job, fast on GPU |
| M2–M4 | Run open-model baselines (the candidates for local mode) on the benchmark | Measures how much quality local mode loses |
| M5 | LoRA fine-tune, **only if** M4 shows a gap | Needs reviewed labels + a benchmark to prove it helped |

Fine-tuning before M3 produces a model you can't evaluate — you'd have no way to tell if it got better. An optional throwaway LoRA run to learn the tooling is fine, as long as its results aren't reported.

---

## 11. Cost (monthly, steady state, estimates)

| Item | Estimate | Notes |
|---|---|---|
| CI (GitHub Actions) | $0 | Keep daily job < ~30 min |
| Postgres | $0 → $25 | Free tier first |
| Etherscan | $0 | Free tier, rate-limited |
| Archive RPC (historical state) | $0 → $50 | Free tiers may be too limited — measure in M0 |
| LLM label proposals + API baselines | $10–50 | Eval runs re-run every baseline |
| Storage (sources, builds, indexes) | $0–10 | |
| Lightning AI | $0 until M5, then $10–60/run | Plus failed experiments |
| **Reviewer time** | **the real cost** | Measured in M0; sets dataset size |

---

## 12. Risks

| # | Risk | L | I | Mitigation |
|---|---|---|---|---|
| R1 | Slither rarely flags the real weakness → triage ceiling low | Med | High | Measured in M0; model can flag beyond Slither; beyond-Slither rate tracked |
| R2 | Label noise | High | High | Separate evidence states; 100% review of eval sets; spot-check rate reported |
| R3 | Eval leakage (retrieval, PoC comments, forks, memorized old code) | High | Critical | §9 items 1–6 |
| R4 | Benchmark biased to fork-replayable code bugs (DeFiHackLabs selection) | High | Med | State it; off-chain incidents tagged and excluded with % reported |
| R5 | Source / build reconstruction fails | Med | High | Funnel tracking; Sourcify fallback; partial-scan reporting |
| R6 | Frontier model + retrieval (B3) is simply the best | Med-High | Med | Fine — Hindsight ships B3 as the API-mode backend; local mode is the privacy option |
| R7 | Data licensing blocks commercial use | Med | High | Apache-2.0 core source; DeFiLlama discovery-only; revisit all sources before any paid release |
| R8 | Dual-use | Med | Med | No exploit generation; no mass scanning of deployed contracts |
| R9 | Solo reviewer bottleneck | High | Med | Dataset size derived from review hours; LLM pre-fill |
| R10 | Running untrusted PoC/build code | Med | High | Disposable sandbox, no credentials (ENR-10) |
| R11 | Small test set → noisy decisions | High | Med | CIs at incident/family level; sealed test used sparingly |

---

## 13. Decisions log (from stress test, 2026-10-22)

| # | Decision | Outcome |
|---|---|---|
| D1 | Purpose | Usable product; open source; commercial option open |
| D2 | Model task | Code + Slither hints + precedent → one ranked list; triage and beyond-Slither scored separately |
| D3 | Differentiator | Fresh, grounded, tool-verified triage; pluggable reasoning model |
| D4 | Fine-tuning | Deferred; learned ranker first |
| D5 | Chain | Ethereum mainnet first |
| D6 | Review | Owner reviews as needed; eval sets 100% reviewed; size set after M0 |
| D7 | Privacy | Local by default; API opt-in |
| D8 | Licensing | Code open source; publish own labels + pointers; only properly licensed sources |
| D9 | Sources | Public, licence-compatible feeds; Serper/Google News for discovery + backfill; X via official API only; no scraping of X or Solodit |
| D10 | Language | Solidity v1, Vyper next |
| D11 | Positioning | Local-first is the headline; precise definition in §1 |
| D12 | Lightning AI | Use credits from M0 for labeling, embeddings, baselines; fine-tune only at M5 |
| D13 | Name | Hindsight; `hindsight-sec` for org/package/domain |
| D15 | **M0 decision (provisional, 2026-10-22; updated after B2)** | **Conditional GO: build the dataset and benchmark (M1, M3). Hold the product model work (M4, M5) behind one more gate.** <br>• Triage-only is dead: Slither's strict coverage is 11%. <br>• A bare frontier model already localizes 70% of known hacks (B2). "LLM reads code" is not a differentiator by itself, so R6/R7 is materializing. <br>• What's still unproven, and is now the gate before M4: does precedent retrieval and freshness beat B2 on **post-cutoff** hacks, and does Hindsight have a lower **false-positive rate** on clean, audited code? M0 can't answer either: post-cutoff n=3, and no clean set has been run. <br>• The dataset and benchmark are useful in every outcome (they're the fallback product in §5), so M1 goes ahead. <br>• Data quality is the cheapest win: 6 of B2's 8 misses came from missing implementation or facet source. Proxy resolution with an Etherscan key and archive RPC comes first in M1. <br>• Still needs a human spot-check of ~10 incidents (`ACTION_ITEMS.md`) before it's final. <br>• **Update after B2 v2 (post-cutoff + clean):** the gap is now concrete. The bare model localizes 77% of post-cutoff exploits in its top 5, but flags only 9% as exploitable. **The M4 gate becomes detection recall at a fixed false-positive rate**, not Hit@5. Hindsight passes if, on post-cutoff exploits mixed with clean code, it flags materially more real exploits than B2 at no more than B2's false-positive rate. Build the clean set from obscure audited contracts before running that gate. |
| D16 | **Precedent spike (2026-10-22): flat** | Same model and blind pool as B2 v2, plus the top-5 past hacks per case. Retrieval was TF-IDF over 830 pre-2026-07 DHL incidents, all EVM chains. Result: <br>• Detection (claims a bug, medium/high) went from **2 to 3 of 23**. <br>• Clean false positives stayed at 0 of 12 (one new low-confidence flag on SwapRouter). <br>• Hit@1 went from 41% to 50%. Hit@5 stayed at 77%. <br>No meaningful lift, but **the retrieval was poor**: <br>• Hubness: 5 generic incidents filled 43 of 175 slots. <br>• Median top-1 similarity was 0.17. <br>• Agents said the precedents rarely informed a verdict. <br>So this tests the crude implementation, not the thesis. **Next decisive test: oracle precedents.** Give the model hand-picked, genuinely relevant past hacks, the best case for retrieval. If detection still doesn't rise, the precedent thesis is dead and the dataset/benchmark fallback applies. If it rises, invest in retrieval quality (code embeddings + the reranker, §7.9) before anything else |
| D17 | **Oracle-precedent test (2026-10-22): no demonstrated lift in this pilot** (reworded after the 2026-10-23 audit; see D18) | Same model, same blind pool. Each case got 5 past hacks **hand-picked** by a labeler who knew the real bug. Clean cases got equally similar-looking past hacks. <br>**Results across no / retrieved / oracle past hacks:** <br>• Exploits flagged (medium/high): 2 / 3 / 3 of 23. <br>• Exploits flagged (any confidence): 5 / 6 / 5 of 23. <br>• **Correct detections (flagged, and top-1 is the bug): 4 / 4 / 3.** <br>• Clean false positives (medium/high): 0 / 0 / 0 of 12. <br>• Hit@5: 17 / 17 / 17 of 22. <br>The same 4–5 incidents are flagged in every run, so the model's verdict depends on the code, not on the past hacks. By the rule set before the test (D16), the pilot fails, but **it is not a definitive rejection**: inputs were incomplete for 8 of 23 exploits, there was one run per condition, the labels are LLM-only, and n is small (D18). **Consequences:** <br>1. Hold all model, reranker and fine-tuning work (§7.9, M4–M5). <br>2. Ship the **fallback product**: a leak-free, point-in-time exploit dataset plus a benchmark (post-cutoff exploits mixed with clean contracts), published openly. M0 found nothing else like it. <br>3. Keep the data work. Proxy, implementation and diamond recovery helps every tool. <br>4. One untested hypothesis remains, and it's a **new** bet, not a rescue: the model ranks the bug in its top 5 77% of the time but won't commit. A *calibration* layer could turn its internal ranking into a usable risk score, measured as ROC across exploit and clean cases. Test it only if you want to keep a tool in scope. <br>Caveats: n = 23 exploits and 12 clean contracts, one model (Sonnet 5.5), LLM labels, and a prompt that warned some cases are clean |
| D18 | **Audit corrections (2026-10-23)** | An external audit found 6 problems. 1, 2, 3, 4 and 5 are fixed; 6 is deferred. <br>(1) The clean inputs bundled unrelated files. The UniswapV3Factory case had 390 files, including a pool with missing owner checks. Inputs are now the target's import closure plus `TARGET.md` (`m0/scripts/b2/scope.py`). <br>(2) The scorer matched on function name only, so `Wrong.sol:withdraw` matched `Victim.sol:withdraw`. It now matches file plus function, with "strict" meaning defect locations only. <br>(3) Missing vulnerable source counted as model failure. Only **15 of 23** exploit cases contain every defect file, and results are now reported on both sets. <br>(4) D17 is reworded. <br>(5) Missing, duplicate or malformed submissions now fail scoring instead of being silently counted as "no bug". <br>(6) Retrieval isn't point-in-time: it reads the current PoC text and has no family exclusion. Label it "exploratory" until that's fixed. <br>**Rescored results** (`m0/b2/rescored_2026-10-23.md`; old predictions, new scorer; the runs saw unscoped inputs): <br>• Strict Hit@5 is 12/22 for all three conditions, not 17/22. On source-complete cases it's 11/15. <br>• Correct detection on source-complete cases: 3 / 3 / 2 of 15. <br>• Clean FP in scope: 0/12 everywhere. The one oracle and spike "false positive" was a bundled out-of-scope file. <br>• Known-hack B2 Hit@5: 17/24 (71%). Slither B0: 7/24 (29%). <br>**The conclusion holds in direction:** no lift from past hacks, and low detection by a bare model. Its strength is "pilot", not "proven". |
| D14 | Reranker | Yes. Off-the-shelf Apache-2.0 cross-encoder first, then fine-tune it on reviewed pairs. Jina excluded for its non-commercial licence |

---

## 14. Open questions

- Code licence for Hindsight itself: Apache-2.0 (matches DeFiHackLabs, patent grant) vs MIT. *Leaning Apache-2.0.*
- Which local model is good enough for local mode? Decide at M4 by benchmark.
- Function-level vs contract-level embeddings — decide at M2 by benchmark.
- Use different LLMs for labeling vs baselines, to avoid self-agreement bias?
- Before any commercial release: DeFiLlama terms, and whether any audit-report source grants reuse.
- When does fork replay (replay_status) become required evidence rather than optional?
- ~~MacBook RAM~~ **Answered:** MacBook Air, 24 GB unified memory, fanless. Local mode targets 7–8B models at 4-bit, with up to ~14B at 4-bit (~9 GB weights) as the ceiling. The Air throttles under sustained load, so it suits scans and inference, not training. M4 benchmarks local mode at these sizes only.
- ~~Lightning AI credit~~ **Answered:** $15. That's small, so it's reserved for the one job a Mac can't do well: fine-tuning the precedent reranker (§7.9). The other jobs moved off Lightning:
  - Label proposals: done by Claude agents in M0.
  - Embeddings and reranker inference: run on the Mac.
- Serper and X API monthly budget.

---

## 15. M0 checklist

Status as of 2026-10-22. Tooling is in `m0/`; how to review is in `m0/review/README.md`.

- [x] Filter DeFiHackLabs to Ethereum mainnet; pick 30–50 incidents stratified by year, category, complexity → 357 incidents, 40-incident sample (`m0/catalog/`)
- [x] Funnel up to the Slither run (Sourcify only) → 42% usable (`m0/funnel/`). The review sample is being prepared the same way, with code-address candidates (`m0/scripts/review/prepare.py`)
  - Missing victim addresses: the catalog parser recovers 5 of the funnel's 25. For the rest, the victim is only in PoC code, so the reviewer or LLM picks it from the candidates.
- [x] Coverage vs DeFiLlama → DHL misses ~half (`m0/gaps/`)
- [x] Blind LLM review of all 40 incidents by Fable 5.1 (`m0/review/reviews.llm.jsonl`, `summary.llm.md`), compared against the Opus proposals → provisional decision D15
- [ ] **Owner:** spot-check ~10 incidents by hand (list in `ACTION_ITEMS.md`), using `review.py --redo <id>`. This is also the only way to measure human review time
- [ ] Time every review (median, p90, worst) → automatic in `summarize.py`
- [ ] Measure **Slither coverage of the causal weakness** → automatic in `summarize.py` once reviews exist
- [x] Run B2 (frontier model, code only) on the same set → Hit@5 70% vs Slither 37% (`m0/b2/`)
- [x] Post-cutoff test set (30 DHL Ethereum incidents from 2026-07 on; 23 with victim source) and a clean set (12 famous audited contracts). B2 v2 measured: Hit@5 77%, detection recall 9%, clean FP 0% (`m0/b2/v2/`)
- [ ] Before the M4 gate: add obscure audited clean contracts, add news-discovered post-cutoff incidents (needs `SERPER_API_KEY`), and resolve proxies and diamonds (needs `ETHERSCAN_API_KEY` and an archive RPC)
- [ ] Run B3-equivalent (Claude Code + Slither-MCP, no exploit DB) on the same set. Blocked on reviews
- [ ] Check archive-RPC free-tier limits for proxy resolution. Blocked on an RPC provider choice
- [ ] Rerun funnel with `ETHERSCAN_API_KEY`. Blocked on the key
- [ ] Run 20 Serper queries over a DeFiHackLabs gap month (2025-12 was the worst: 6 missed, 0 found). Blocked on `SERPER_API_KEY`
- [ ] Write the numbers into §5 targets and §6 M1 size; go / no-go

---

## 16. Name shortlist

| Name | Idea | Collision check (2026-10-22) |
|---|---|---|
| **DejaVuln** | "I've seen this bug before" | Free on PyPI; no Solidity repos named this |
| **Precedent** | Every flag cites a real past case | PyPI name taken → `precedent-sec` |
| **Casefile** | A file of past cases per finding | PyPI name taken |
| **Hindsight** | Learn from past hacks | PyPI taken; also an existing forensics tool |
| **Recur** | Bugs recur; we catch the repeats | `recur-sec` free on PyPI |
| **Postmortem** | Built from post-mortems | Generic; hard to search |

**Chosen: Hindsight** (D13, 2026-10-22).
- Use `hindsight-sec` for the GitHub org, PyPI and npm package, and domain. All looked free on 2026-10-22. The bare names are taken.
- The CLI command can still be `hindsight`.
- Known collision: an existing browser-forensics tool called Hindsight. Always write "Hindsight for smart contracts" in the README and listings so search results don't mix them up.
- **DejaVuln dropped:** it's the name of a known 2024 LG webOS TV root exploit.
- Not checked: trademarks. Do a quick search before any commercial release.
