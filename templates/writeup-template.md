# <MachineName> — Writeup

| Field | Value |
|-------|-------|
| **Machine** | <MachineName> |
| **OS** | Linux / Windows |
| **Difficulty** | Easy / Medium / Hard / Insane |
| **Released** | YYYY-MM-DD (retired / active) |
| **IP** | 10.x.x.x (VPN `tun0`) |
| **Owned** | YYYY-MM-DD — User ✅ Root ✅ |
| **Time** | ~X minutes/hours |

**Attack path (TL;DR):**

```text
<one-line chain: service → vuln → foothold → privesc>
```

---

## 1. Recon

```bash
htb machine spawn <name>
nmap -sC -sV -oA recon <IP>
```

| Port | Service | Version | Notes |
|------|---------|---------|-------|
| | | | |

## 2. <Service/Vuln name>

What I saw:

```bash
<command>
```

**Why it worked:** <concept in 1-2 lines — this is the part that teaches.>

```bash
<exploit commands>
```

## 3. Foothold

```bash
<how you got shell / user flag>
```

```
<user flag>
```

## 4. Privilege escalation

Checks run:

```bash
sudo -l
find / -perm -4000 2>/dev/null
getcap -r / 2>/dev/null
```

The winner: <which check hit>

**Why it worked:** <privesc concept>

```bash
<privesc commands>
```

```
<root flag>
```

## Key takeaways

1. <reusable lesson 1>
2. <reusable lesson 2>
3. <what you'd do faster next time>

## Tools used

`nmap` · `...`
