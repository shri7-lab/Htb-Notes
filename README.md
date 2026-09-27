# Htb-Notes

Beginner-friendly Hack The Box writeups — every machine documented step-by-step with exact commands, my thought process, and lessons learned.

> **Goal: HTB Top 50** — this repo will hold every machine I own until I get there.

## How to read these writeups

Each writeup follows the same structure:

1. **Recon** — what the machine tells us
2. **Attack path** — how each door opened, command by command
3. **Why it worked** — the concept behind the trick (IDOR, PCAP analysis, Linux capabilities, etc.)
4. **Key takeaways** — what I'd reuse on the next box

If you're new to HTB: read the **Why it worked** sections first — the commands are easy to copy, but the *reasoning* is the actual skill.

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
