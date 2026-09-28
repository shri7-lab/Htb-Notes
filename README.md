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
6. **Flags** — never pasted; *where* to read them and how to submit
   (regenerating them by re-running is the actual review)
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
htb machine active       # IP source of truth — never trust a copied IP
nmap -sC -sV -p-        # full port sweep first, never a default list
parallel enumeration    # independent surfaces (web/NFS) at the same time
version → CVE search    # fingerprint the app before writing any exploit
manual browsing         # JS, cookies, params — understand the app first
exploit ONLY on target  # authorized HTB scope, always
ONE tunnel only        # same cert + two openvpn = same pushed IP = both die;
                       # pick Mac OR container, the other rides its routes
hosts on BOTH sides    # respawn = new IP → rewrite /etc/hosts (container + host)
ss -tlnp after foothold # loopback services are invisible to remote nmap -p-
```

## After a Mac reboot (session resume checklist)

```text
docker start kali                     # verify container is Up
osascript -e 'do shell script "/usr/local/opt/openvpn/sbin/openvpn \
  --config /Users/abcd/htb.ovpn --daemon --log /tmp/mac-vpn.log" \
  with administrator privileges'      # 1 password prompt → utun tunnel
htb machine active                    # no active machine → spawn; NEW IP →
                                      # rewrite /etc/hosts on BOTH sides
curl -sI http://orion.htb/            # must be 200 from Mac AND from kali
```

## Rules (non-negotiable)

- Targets are **only** HTB machines, my own labs, or explicitly authorized scopes.
- No scanning/exploiting anything else — ever.
- **No flags in notes.** Flag values are never committed — write *where*
  they were read instead. If you can answer from the notes without
  re-running the box, the notes are doing the learning for you.

---

*Notes maintained by [shri7-lab](https://github.com/shri7-lab).*
