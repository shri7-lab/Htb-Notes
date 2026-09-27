# Htb-Notes

Beginner-friendly Hack The Box writeups — every machine documented step-by-step with exact commands, my thought process, and lessons learned.

> **Goal: HTB Top 50** — this repo will hold every machine I own until I get there.

## How to read these writeups

Each writeup follows the same structure:

1. **The Thought Process** — har step ka *WHY*: kis order mein kyun, pehla kadam kaise socha
2. **Recon** — kya mila, non-standard flags tode hue (2-line explainer)
3. **Dead Ends** — kya try kiya, kya fail hua, kyun (real hacking me ~70% yahi hai)
4. **Vulnerability ELI5** — har vuln ek aam-bhasha analogy se (jaise IDOR = hotel key)
5. **Exploitation** — exact commands jo terminal mein actually chale
6. **Flags** — user + root
7. **Patch / Remediation** — developer/sysadmin isko kaise rok sakta tha

If you're new to HTB: **Thought Process** aur **Dead Ends** sections
padho — commands toh copy ho jaate hain, *soch* hi asli skill hai.

## Machines

| # | Machine | OS | Difficulty | Date | Status |
|---|---------|----|-----------|------|--------|
| 1 | [Cap](writeups/cap/README.md) | Linux | Easy | 2026-09-27 | ✅ User + Root |
| 2 | [Enigma](writeups/enigma/README.md) | Linux | Easy | 2026-09-27 | ✅ User + Root |

**Progress: 2 / Top 50 journey**

## Methodology I follow

```text
htb machine spawn          # machine lete hi IP
nmap -sC -sV -oA recon     # full port sweep pehle
gobuster / dirb            # web content
manual browsing            # JS, cookies, params — samjho kya hai
exploit ONLY on target     # authorized HTB scope, hamesha
```

## Rules (non-negotiable)

- Targets are **only** HTB machines, my own labs, or explicitly authorized scopes.
- No scanning/exploiting anything else — ever.

---

*Notes maintained by [shri7-lab](https://github.com/shri7-lab).*
