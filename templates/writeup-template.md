# [Box Name] — Active Learning Writeup

| Target | Detail |
| :--- | :--- |
| **OS** | Linux / Windows |
| **Difficulty** | Easy / Medium / Hard |
| **IP Address** | `10.129.X.X` (VPN `tun0`) |
| **Owned** | YYYY-MM-DD — User ✅ Root ✅ |
| **Key Concepts** | e.g., IDOR, Linux Capabilities, FTP Sniffing |
| **Time** | ~X min |

**Attack path (TL;DR):**

```text
<one-line chain>
```

---

## 1. Reconnaissance & Surface Analysis

### Tunnel Sanity (before the first packet)

```text
htb machine active     # the ONLY IP source of truth (never copy IPs from chat)
docker exec kali …     # all target traffic — the VPN (tun0) lives in the container
/etc/hosts <ip> <name> # vhost mapping: inside container AND on the host browser
```

### Raw Port Scan

```bash
nmap -sC -sV -oA recon/initial 10.129.X.X
```

```text
-sC : run default scripts (banner grabbing / light enum — no manual guessing)
-sV : detect service versions (needed later for CVE search)
-oA : save output in three files (txt + nmap + gnmap)
```

### Initial Observations

- **Port XX (Service):** what looks anomalous about this service/version?
- **Port YY (Service):** is anonymous access or an exposed management panel likely?

### 🧠 Pause & Predict

<details>
<summary><b>Think first:</b> before touching any tool — which port has
the widest attack surface and why?</summary>

Port 80/HTTP is usually the first pick: web applications expose custom
logic (IDOR, injection, forgotten endpoints), while hardened network
services like SSH/FTP rarely give anything without credentials.
Brute-forcing SSH first is a time sink.
</details>

## 2. Enumeration & Finding the Seam

### What I Investigated

```text
Command structure:
<tool> <target-flags> <payload/wordlist>

# Example:
curl -s http://10.129.X.X/data/1
```

### 🧠 Interactive Challenge

<details>
<summary><b>Challenge:</b> the URL shows <code>/data/1</code> — as an
attacker, what is the first test you run and why?</summary>

Tamper the parameter and request adjacent IDs (<code>/data/0</code>,
<code>/data/2</code>). Initial/default records usually live at index 0
or the admin ID. If a neighboring object loads without authenticating
as its owner, object-level authorization is missing (IDOR).
</details>

### ❌ Failure Log — What I Tried First & Why It Failed

> Mandatory section. In real engagements ~70% of attempts fail — this
> log is what builds troubleshooting memory.

1. Ran `<command>` → **Result:** `<error/empty output>`.
   *Takeaway:* `<what this taught, why I moved to the next vector>`
2. Ran `<standard check>` → **Result:** nothing interesting.
   *Takeaway:* `<...>`
3. Finally ran `<next tool>` → **HIT.**

### The Breakthrough (Root Cause Breakdown)

**The Flaw:** `<vulnerability name, explained without jargon>`

**Real-World Analogy:**
> `<two-line story: hotel key / valet / receptionist style>`

<details>
<summary><b>🧠 Mini-challenge:</b> if the URL is
<code>http://target/item/5</code>, which test proves whether access
controls exist?</summary>

Request adjacent values (<code>/item/0</code>, <code>/item/1</code>,
<code>/item/-1</code>). If their data loads without re-authenticating
as that owner, object-level authorization is missing.
</details>

## 3. Foothold (Initial Access)

### Command Breakdown

> Skeleton first, execution second — no copy-paste ghosts.

```text
Syntax structure:
tshark -r <file> -Y <display_filter> -T fields -e <field_name>
```

<details>
<summary><b>Task:</b> extract only FTP usernames and passwords from a
capture — what does the filter expression look like?</summary>

<code>-Y ftp.request.arg</code> — FTP credentials travel as command
arguments (USER/PASS), which land in the <code>ftp.request.arg</code>
field. <code>-T fields -e ...</code> strips packet noise and prints
only that value.
</details>

```bash
tshark -r capture.pcap -Y ftp.request.arg -T fields -e ftp.request.arg
```

```text
-r capture.pcap : read from an offline capture file (not a live interface)
-Y "..."       : Wireshark display filter — keep only matching packets
-T fields -e   : print only the requested field, nothing else
```

### Credentials Found

```text
username : password
Access Vector: FTP / SSH / Web
```

## 4. Privilege Escalation

### Internal Audits (order matters)

```bash
sudo -l                                 # sudo rules?
find / -perm -4000 -type f 2>/dev/null  # SUID binaries?
getcap -r / 2>/dev/null                 # file capabilities?
```

### The Misconfiguration

- **Binary:** `/path/to/binary`
- **Dangerous Permission:** `cap_setuid+eip` / sudo misconfig / ...

### 🧠 Privesc Reasoning

<details>
<summary><b>Q:</b> why is giving <code>cap_setuid</code> to an
interpreter (Python/Perl) worse than to a compiled utility?</summary>

An interpreter runs arbitrary system calls straight from an inline
one-liner — no compilation step. Python + <code>cap_setuid</code> means
any unprivileged user runs <code>os.setuid(0)</code> and inherits root
instantly.
</details>

### Root Exploitation

```bash
<exploit command>
whoami   # root
```

## 5. Flags

> **Rule: never paste flag values into notes.** They turn the writeup
> into a flashcard (passive recognition). Record *where* the flag was
> read and *how* it was submitted — regeneration is the review.

```text
user: <path/command that printed it>   (submitted ✓)
root: <path/command that printed it>   (submitted ✓)
```

```bash
htb machine own <flag>
```

## 6. Defense & Remediation (The Sysadmin View)

| Stage | Issue | Secure Fix |
| :--- | :--- | :--- |
| Web | `<predictable IDs / missing ownership check>` | `<server-side session ownership check + UUIDs>` |
| Network | `<plaintext protocol>` | `<SFTP / HTTPS>` |
| OS | `<capability / sudo misconfig>` | `<setcap -r / tighten sudoers>` |

## 7. Key Takeaways

1. `<reusable lesson>`
2. `<what becomes faster on the next box>`

## 8. 🧠 Active Recall Challenges (Before You Close This Box)

- [ ] **Challenge 1:** `<reverse question — what would you do without the tool?>`
- [ ] **Challenge 2:** `<hands-on lab to reproduce on local Kali>`
- [ ] **Challenge 3:** re-run this box with zero notes — reach user in `<X min>`?

<details>
<summary><b>Answers</b> (attempt first, then open)</summary>

1. `<answer>`
2. `<answer>`
3. `<answer>`
</details>

---

**Final Checklist (before publishing):**
- [ ] Could a newcomer parse every command? (flags broken down)
- [ ] Is the *WHY* of the first move explained?
- [ ] Are failures documented (not just the perfect path)?
- [ ] Does command order match what actually ran in the terminal?
