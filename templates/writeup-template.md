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

## 1. The Thought Process (dimaag kaise chala)

> Beginner confusion: "Scan ke baad seedha port 80 pe kyun gaya? 21 pe kyun nahi?"

<Har step ka **WHY** — kis order mein kya kiya aur kyun. Example:>

Nmap me X ports mile: 21 (FTP), 22 (SSH), 80 (HTTP).
SSH brute-force time-waste hai jab tak creds na milein.
Isliye pehle80 explore kiya kyunki web apps me logical errors
(IDOR, SQLi) milne ke chances sabse zyada hote hain...

## 2. Recon

```bash
htb machine spawn <name>
nmap -sC -sV -oA recon <IP>
```

<Non-standard flags ka 2-line explainer, seedhe command ke neeche:>

```text
-sC  : default scripts chalao (banner, enum — khud guess mat karo)
-sV  : service versions detect karo (CVE search ke liye version chahiye)
-oA  : output ko recon.* files mein save (txt/nmap/gnmap teeno)
```

| Port | Service | Version | Notes |
|------|---------|---------|-------|
| | | | |

## 3. Dead Ends (kya try kiya, kya fail hua)

> Real hacking me ~70% cheezein fail hoti hain — failures se hi seekh
> milta hai. Jhooth: "sab pehli baar chal gaya."

- <kya try kiya → kya error aaya → kyun fail → agla kadam kyun chuna>
- <standard checks jo khaali nikle (sudo -l, SUID...) — unhe bhi likho,
  kyunki yahi checks agli baar speed dete hain>

## 4. <Vulnerability naam> — ELI5

> Vuln ka naam likh kar aage mat badho —1 line aam bhasha mein:

<Example style:>

"IDOR ka matlab: hotel me room101 ki key se room102 bhi khul jata hai
kyunki guard (server) check hi nahi karta key kiski hai..."

<Har key vuln ke liye aisa ek analogy do.>

## 5. Exploitation

<Yahan actual commands, har non-standard command ke flags tode hue:>

```bash
<command>
```

```text
-r file     : capture file padho
-Y filter   : sirf <x> wale packets dikhao
-T fields   : extra headers hata ke sirf chahiye wali value print karo
```

**Why it worked:** <concept in 1-2 lines>

## 6. Flags

```text
user: <flag>
root: <flag>
```

```bash
htb machine own <flag>
```

## 7. Patch / Remediation (fix kaise karein)

> Ethical hacker aur script-kiddie me yahi farak hai — hamesha likho
> ki developer/sysadmin isko kaise rok sakta tha:

- <vuln1 ka fix — code/config level>
- <vuln2 ka fix>
- <privesc vector ka fix>

## Key takeaways

1. <reusable lesson>
2. <agli baar kya faster hoga>

## Final Checklist (note se pehle khud se poocho)

- [ ] Kya naya banda command ka syntax samajh payega?
- [ ] Kya maine bataya ki shaq kaise hua (pehla kadam kyun)?
- [ ] Kya commands ka order wahi hai jo terminal me actually chala?

## Tools used

`nmap` · `...`
