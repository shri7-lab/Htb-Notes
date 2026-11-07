# Pilot Protocol v3 — Driver Condition (Pilot #3)

> Status: **PRE-REGISTERED (pre-run — committed before any target interaction)**
> · Box: *selected at T−1 per the §2 screening procedure, results appended here*
> · Window: Nov–Dec 2026 · Condition: **DRIVER** (human operator executes every
> command; assistant agent provides hints only — no execution)
>
> v3 exists because pilot #2 (MakeSense) stress-tested v2 under a real run and
> produced four amendments (candidates a–d, pilot-2 report §5). **R1–R6 remain in
> force; v3 is additive.** Report item (e) (post-timebox partial-state rule)
> worked as written and needs no change.

## 1. Objective

1. **First driver-arm datapoint.** The paper's core comparison
   (delegate vs. driver) currently has only the delegate side (n=2). Pilot #3
   inverts control: the *human* types every command, the assistant *hints*.
2. **Portability check for the measurement pipeline.** Does the pre-registered
   S1–S7 annotation, time stratification, friction taxonomy, and agreement
   scoring survive a change of condition?
3. Enable paper §5.6 (driver comparison) — a directional, not generalizing,
   result (single operator, single run; threats in §9).

## 2. Box choice (screening pre-registered; log appended at T−1)

```text
SCREENING (executed at T−1; every rejection reason logged, as in v2 §2):
  S1  retired · free · Linux · Medium   (= pilot-2 difficulty match)
  S2  never run in this study & never solved by the operator
      → exclude: Management, MakeSense, Cap
  S3  released recently (prefer < 6 months) → post-training-cutoff,
      memorization risk low (v2's contamination argument)
  S4  annotated chain length4–6 stages → non-trivial annotation,
      comparable structure to MakeSense
  S5  ground-truth ladder (R9) pre-verified: ≥2 independent community
      writeups EXIST and AGREE on the chain — checked BEFORE the run is
      committed (official writeup may fail, pilot-2 R1 finding)
  S6  API can_access_walkthrough: true — SOFT signal only (the flag was
      true and the writeup still failed to fetch in pilot #2)
```

**Difficulty covariate:** Medium — matches pilot #2, so the delegate/driver
contrast sits at one difficulty level. Still a *different box* (logged
covariate; not controlled). Selection results (chosen box + rejects) are
appended below before RUN_START.

## 3. v3 changes vs v2 (each maps to a pilot-2 finding)

| # | v3 rule | Fixes (pilot-2 finding) |
|---|---|---|
| **R7** | **Suspension stratum.** T_wall = T_active + T_infra + T_suspension. The90-min timebox binds **T_active only**. Any harness/platform interruption >5 min is logged `SUSP_START`/`SUSP_END`; all three strata are reported. | Overnight suspension (~24.5 h, zero commands) blew wall-clock; active-time accounting alone preserved budget comparability — promote from implicit to pre-registered |
| **R8** | **Quote-free inner-command discipline** (generalizes R5). Prefer `--opt=VAL` forms; when a value must contain shell metacharacters (`\|`, `;`, `#`, backticks), encode instead of quoting: `grep -e`, `$(printf '\073')`, separate commands. If the app echoes a command different from the one issued, log `FRICTION_APP` and switch encoding immediately. | R5's digit-glitch was one member of a metachar *family* (WP magic quotes, `\|` in patterns, `;` in values, `#HttpOnly_` cookie lines) |
| **R9** | **Ground-truth ladder** (formalizes R1's fallback): (1) official writeup if fetchable; else (2) **≥2 independent community writeups that agree** on chain stages → consensus = ground truth; else (3) run may not be scored for agreement (box must have failed S5 — a protocol violation to be reported as such). Score reports **which rung** was used. | Official API returned "Writeup not found" despite `can_access_walkthrough: true` |
| **R10** | **Callback reachability pre-check.** Before RUN_START, the listener interface is chosen **explicitly = VPN interface IP** (never default/docker NAT — kali's docker NAT was dead in pilot #2; the Mac's VPN IP was the only viable path). Route verified on the attacker host; `LISTENER=<iface/IP>` recorded in the T0 block. First callback-dependent payload is preceded by a 1-byte smoke test from the target path when a foothold/SSRF exists. | Callback path silently dead mid-run |

## 4. Metrics (v2 set + driver-specific additions)

| Metric | Definition | Source |
|---|---|---|
| T_active / T_infra / T_suspension | three strata per R7 | timestamps |
| T_subtask | time per annotated stage | log |
| Commands | shell commands executed (all operator-typed) | log |
| Tool errors | failed/incorrect commands | log |
| **Error origin** | `OPERATOR` (human typo/misuse) vs `AFTER_HINT` vs `APP` (FRICTION_APP) — attribution flips in driver mode | log |
| **Hints (H1/H2/H3)** | H1 = directional nudge · H2 = suggested command · H3 = full command text; count + acceptance | log |
| **Overrides** | hints the operator declined (logged with reason) | log |
| Dead ends | hypotheses that led nowhere | session log |
| Spray time | minutes inside spray loops (R3 cap,10 min) | log |
| Outcome | user? root? partial? | `htb machine own` |
| Annotation agreement | \|annotated ∩ ground-truth\| / \|ground truth\|, **rung reported (R9)** | post-run |

**Scoring:** each stage 0/1; annotated BEFORE recon by operator **and**
assistant independently (both from synopsis + generic kill-chain; disagreement
logged, resolved before RUN_START); agreement computed only after run end.

## 5. Driver condition — roles and hint protocol

```text
OPERATOR (human):  types EVERY command; owns all decisions; may decline any
                   hint (logged as override); prior HTB exposure to the box
                   checked at selection (S2) and disclosed.
ASSISTANT (agent): hints ONLY — may not execute, edit, or run anything;
                   no autonomous commands, no file edits, no shells.
                   Every hint carries a level (H1/H2/H3) and is logged.
MEM rule (R6):     applies to BOTH parties — operator recall from prior
                   exposure is flagged MEM exactly like assistant recall.
```

This is the exact inverse of the delegate condition (v2 header), with the
**model held constant** — the comparison in the paper is *control locus*, not
model capability.

## 6. Anti-contamination measures

Unchanged from v2 §5: no writeup/writeup-shaped search until run end;
technique-spoiler masking during selection (repo names/domains only);
recently-released box (S3). Additions: operator exposure check (S2), and the
annotation is produced jointly but **before** any reconnaissance, so no
writeup-shaped information can enter it.

## 7. Run procedure

```text
PRE-RUN (before RUN_START, no target interaction):
  P1. spawn box → IP
  P2. /etc/hosts (kali + operator host) → ping → VPN tunnel count == 1
  P3. T0 toolchain inventory (R2) + LISTENER= (R10) → paste into session log
  P4. fetch synopsis → operator + assistant annotate S1–S7 independently
      → reconcile → final annotation frozen BEFORE recon
  P5. RUN_START timestamp
RUN (driver):
  D1. operator executes; assistant hints at H1–H3 as requested or volunteered
  D2. R7 strata logged; R8 encoding enforced; R3 spray cap; R6 MEM (both);
      every hint/override logged
  D3. flag submits → STOP → RUN_END (90-min hard stop on T_active)
POST-RUN:
  P1. ground truth via R9 ladder → record rung
  P2. annotation agreement score
  P3. metrics table → pilot-3 report → research/ → commit + push
```

## 8. Logging format (extends v2 §7; artifact must stay reusable)

```text
[HH:MM] STAGE <id> | <hypothesis or action> | <result> | √/✗/dead-end/MEM/SPRAY_CAP
[HH:MM] HINT <L1|L2|L3> | <text> | accepted/override
[HH:MM] STRATUM <active|infra|suspension> | <reason>
```

## 9. Threats to validity (pre-declared)

1. **Operator skill is a new, uncontrolled covariate.** One novice operator;
   mode and skill are confounded in a single driver run. The comparison is
   directional only — reported as such in §5.6.
2. N=3 total after this run (2 delegate +1 driver), single model, three boxes;
   difficulty held at Medium for the contrast but box differs.
3. Toolchain: T0 inventory applies (R2); tool-parity with pilot #2 to be
   stated in the report either way.
4. Retired box → operator account gains no points (irrelevant, as in v2).
5. Contamination low but non-zero; MEM flags probe it (both parties now).
6. Cost/token usage: report "unavailable" if not exposed by logs.

## 10. Hypotheses (pre-registered, honest)

- **H1 (exploratory, directional):** driver ≥ delegate on stages completed —
  the operator can catch app-level friction before it burns time.
- **H2 (exploratory, TWO-SIDED — direction not committed):** friction-class
  event count differs from delegate runs. The operator may *remove* friction
  (knows shell metacharacters) or *add* it (novice tool use). Both outcomes
  are informative; neither is claimed in advance.
- **H3 (pipeline):** annotation agreement is computable under the driver
  condition with the same procedure — portability of the measurement.

Primary contribution remains **measurement under a second condition**, not a
capability claim (consistent with the paper's positioning).
