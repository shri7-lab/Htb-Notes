# Paper skeleton — agentic AI pentesting (empirical/system)

> **Target:** COLM2027 (submit ~Mar 2027) · fallback: SaTML / ACSAC
> **Preprint:** arXiv first (~Feb 2027) · **Disclosure:** LLM-originated
> ideas/content/eval will be disclosed per COLM policy (author statement in §7).
> **Status legend:** ✅ done · 🟡 partial · ⬜ pending · 🚫 blocked

---

## Working titles

1. *Pre-Registered Evaluation of LLM Agents on Capture-the-Flag Pentesting:
   Protocols, Annotation Agreement, and a Dead-End Taxonomy*
2. *Two Arms, One Box: Measuring Delegate vs. Driver-Mode LLM Pentest Runs
   under Pre-Registered Protocols*

## Abstract (draft skeleton) 🟡

- Problem: agentic pentest evals are under-specified, contamination-prone,
  process-unauditable (⬜ polish after final runs)
- What we did: pre-registered v1→v3 protocols; N runs across 2 conditions
  (delegate / driver); per-stage annotation (S1–S7) scored against ground
  truth (⬜ n=2 → target n≥6)
- Key results (fill after runs): first annotation-agreement measurement
  (7/7 structural coverage, MakeSense) · dead-end taxonomy (6 genuine +
  ~12 friction events) · process stratification 34/34/22/10
- Honest limits: difficulty covariate uncontrolled, n small, LLM assistance
  disclosed

##1. Introduction ⬜

- Agentic AI for pentesting: hype vs. measurable reality
- Contribution list (4): (1) pre-registered protocol series v1→v3 with
  suspension/metagchar/ground-truth amendments, (2) annotation-agreement
  metric, (3) dead-end + friction taxonomy, (4) two-condition comparison

##2. Related work 🚫 blocked (websearch402 — quota unblock ke baad)

- LLM pentest agents (AutoPentest, PentestGPT-class, CTF benchmarks)
- Evaluation methodology / contamination controls
- Human-AI collaboration modes (delegate vs. supervisory)

##3. Methodology ✅ (mostly draftable from pre-registered docs)

- 3.1 Protocol series: v1 (`0412831`) → v2 (`bc743eb`, R1–R6) → v3
  (⬜ pre-register: suspension stratum, quote-free rule, ground-truth
  ladder, callback reachability)
- 3.2 Conditions: **delegate** (assistant solo, observer silent) vs
  **driver** (human executes, assistant hints) ⬜ pilot #3 design
- 3.3 Annotation: S1–S7 pre-registered before recon; agreement =
  stage-coverage vs ground truth (official writeup → ≥2 community
  fallback ladder)
- 3.4 Metrics: T_active / T_infra / T_suspension strata, commands,
  dead-end taxonomy, MEM contamination flags, spray caps
- 3.5 Anti-contamination: no writeup read until RUN_END; MEM flags;
  technique-spoiler-free box selection

##4. Experiments 🟡

| # | Box | Cond. | Difficulty | Stages | Flags | Status |
|---|-----|-------|-----------|--------|-------|--------|
| 1 | Management | delegate | Easy (active) | 2/7 | 0 | ✅ `pilot-report.md` |
| 2 | MakeSense | delegate | Medium (retired) | 5.5/7 | user ✓ | ✅ `pilot-2-report.md` |
| 3+ | ⬜ TBD retired boxes + human arm | driver | mixed | — | — | ⬜ design + runs |

- ⬜ Target: n≥6 runs, both conditions, ≥2 difficulties

##5. Results ⬜ (fill as runs land)

- 5.1 Annotation agreement (n=1 so far: 7/7 structural,100% coverage)
- 5.2 Failure/dead-end taxonomy (upload-blocked, SSRF-oracle-useless,
  fuzzing-DoS, spray-exhausted, flavor-cred, injection-cleared + friction
  class: magic-quotes/metachar, nonce-format, cookie-jar, digit-glitch)
- 5.3 Process stratification & time accounting (incl. overnight
  suspension as protocol stress test)
- 5.4 Condition comparison (delegate vs driver) ⬜ needs pilot #3+

##6. Discussion ⬜

- Environment ≠ model: harness/app-mediated command corruption as a
  recurring failure class
- Credential-reuse compound finding (1 password → MySQL+SSH+Basic-auth)
- Tool-parity caveat (java/msf present in pilot #2, absent in #1)

##7. Threats to validity / honesty 🟡

- n small · difficulty covariate · box selection bias · ground-truth
  source deviation (official API failed → community consensus)
- **LLM disclosure statement** (COLM policy) ⬜ write explicitly

##8. Conclusion ⬜

## References ⬜ (after §2 unblocks)

## Appendix: artifact links ✅

- `research/pilot-protocol.md` (v1) · `pilot-protocol-v2.md` (v2)
- `pilot-session-log.md` · `pilot-2-session-log.md`
- `pilot-report.md` · `pilot-2-report.md`

## COLM review-dimension checklist

| Dimension | Evidence | Status |
|---|---|---|
| Empiricism/Evaluation | pre-registered protocols, N runs, agreement metric | 🟡 n low |
| Technological Impact | failure taxonomy → reproducible eval practice | 🟡 |
| Ambition | two-condition, contamination-controlled live evals | 🟡 |
| Understanding Depth | friction-vs-model-error separation, strata accounting | ✅ |
| Clarity/Honesty | LLM disclosure, deviations logged | 🟡 §7 pending |

---

## Timeline (from pilot-2 report §7)

- ✅ pilots #1–#2 · ⬜ v3 + pilot #3 design (this week)
- ⬜ runs Nov–Dec · ⬜ analysis + full draft ~mid-Jan
- ⬜ arXiv ~mid-Feb · ⬜ **COLM submit ~Mar 2027**
