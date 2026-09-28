# Htb-Notes

Beginner-friendly Hack The Box writeups — not command dumps, but
**active-learning notes** that make you think before you read.

> **Goal: HTB Top 50** — this repo will hold every machine I own until I get there.

## How to read these writeups

These notes are built to defeat the "illusion of competence" (reading
is not knowing). Every writeup follows the same structure:

1. **Pause & Predict** — collapsible questions *before* each solution;
   answer hidden under `<details>` so your brain runs first
2. **Recon & Observations** — raw output plus "what looked anomalous
   and why", with every non-standard flag broken down
3. **❌ Failure Log** — what I tried first, the exact error, and the
   takeaway (real engagements fail ~70% of the time — this is where
   debugging memory is built)
4. **The Breakthrough** — the flaw explained in plain language with a
   real-world analogy (no jargon walls)
5. **Syntax Skeleton → Task → Execution** — command structure first,
   a challenge to predict the filter/flag, then the real command
6. **Flags** — user + root
7. **Defense & Remediation** — how a sysadmin/developer kills each
   stage of the chain
8. **Active Recall Challenges** — 3 homework tasks with hidden
   answers; do them *before* closing the tab

**Rule for readers:** if you only scroll, you learn nothing. Open a
challenge, answer it mentally, *then* expand the spoiler.

## Machines

| # | Machine | OS | Difficulty | Date | Status |
|---|---------|----|-----------|------|--------|
| 1 | [Cap](writeups/cap/README.md) | Linux | Easy | 2026-09-27 | ✅ User + Root |
| 2 | [Enigma](writeups/enigma/README.md) | Linux | Easy | 2026-09-27 | ✅ User + Root |
| 3 | [Orion](writeups/orion/README.md) | Linux | Easy | 2026-09-28 | ✅ User + Root |

**Progress: 3 / Top 50 journey**

## Methodology I follow

```text
htb machine spawn        # spawn → grab the IP
nmap -sC -sV -p-        # full port sweep first, never a default list
parallel enumeration    # independent surfaces (web/NFS) at the same time
version → CVE search    # fingerprint the app before writing any exploit
manual browsing         # JS, cookies, params — understand the app first
exploit ONLY on target  # authorized HTB scope, always
```

## Rules (non-negotiable)

- Targets are **only** HTB machines, my own labs, or explicitly authorized scopes.
- No scanning/exploiting anything else — ever.

---

*Notes maintained by [shri7-lab](https://github.com/shri7-lab).*
