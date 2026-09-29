# DarkZeroReturns — Active Learning Writeup

| Target | Detail |
| :--- | :--- |
| **OS** | Hybrid — Linux front (Ubuntu/nginx) + Windows AD lab (`darkzero.ext` ↔ `darkzero.htb`) |
| **Difficulty** | Hard |
| **IP Address** | `10.129.52.73` (VPN, final respawn) |
| **Owned** | 2026-09-30 — User ✅ Root ✅ |
| **Key Concepts** | Handlebars AST injection (CVE-2026-33937), Gitea Actions PR race (CVE-2026-58443), Kerberos SSO, `ksu` keytab abuse, cross-forest golden ticket (extra-SIDs), `SeBackupPrivilege` hive dump, DCSync ×2, Pass-the-Hash |
| **Time** | ~7 h active (split over 2 days + 1 mid-session respawn) |

**Attack path (TL;DR):**

```text
register → SSTI hunt (long wall) → CVE-2026-33937 AST injection → RCE (darkzero)
→ keytab + writeup creds → Gitea SSO → fork→workflow→PR race → svc-runner SSH (user)
→ ksu root (SRV01) → DA creds cracked from SQL backup → DCSync darkzero.ext
→ cross-forest golden ticket (Backup Operators) → DC01 registry hives via SeBackup
→ DC01$ machine hash → DCSync darkzero.htb → PtH → root.txt (root)
```

---

## 1. Reconnaissance & Surface Analysis

### Tunnel Sanity (before the first packet)

```text
htb machine active     # the ONLY IP source of truth (never copy IPs from chat)
docker exec kali …     # all target traffic — the VPN (utun4) lives on the Mac
/etc/hosts <ip> <name> # vhost mapping: inside container AND on the host browser
```

Spawn gave **no IP for ~2 min** (`IP: Not spawned` despite "deployed") — an
empty-IP entry even slipped into `/etc/hosts` and had to be cleaned. Patience
plus one source of truth; never poll random ports while the queue drains.

### Raw Port Scan

```bash
nmap -sC -sV -p- -T4 -oA recon/initial 10.129.52.73
```

```text
-sC : default scripts (banner, titles, light enum — best time/value ratio)
-sV : version detection → CVE search needs exact versions
-p- : all 65535 ports — never assume a standard list
-T4 : just-booted boxes retry slowly; T4 keeps the sweep reliable
-oA : txt + nmap + gnmap — different tools want different formats
```

### Initial Observations

- **22/tcp OpenSSH 9.6p1 (Ubuntu)** — banner says *Linux*.
- **80/tcp nginx 1.24.0 (Ubuntu)** — everything else filtered (host firewall).
- **Metadata ≠ reality:** HTB labels this machine *Windows*. The scan says
  Linux front. Prediction: reverse proxy → Windows/AD backend reachable only
  *through* the front.

### 🧠 Pause & Predict

<details>
<summary><b>Think first:</b> metadata says Windows, scan says Ubuntu. Which
do you trust and what does that imply for the attack plan?</summary>

The scan. The OS field is the author's label; packets are ground truth.
nginx + `302` to a vhost is the classic "front door" pattern — everything
interesting (app, then AD) sits behind it, so web enumeration first, and
keep an AD-lab hypothesis alive for later phases.
</details>

## 2. Enumeration & Finding the Seam

### What I Investigated

```text
curl -sI http://10.129.52.73/            → 302 http://dzcampaigns.htb/
# vhost in hosts (container + Mac), then Host-followed requests:
curl -s http://dzcampaigns.htb/login      → "DarkZero Campaigns" login + /register
```

```text
Set-Cookie: dz.sid = s%3A<id>.<HMAC>  ← express-session SIGNED cookie (Node.js)
                                        = HMAC(secret, sessionid) → forgeable IF secret leaks
ROUTES: / /essentials /dice /login /register /campaign/1 (ID param!)
```

- **Open registration** → self-serve account = guaranteed foothold surface.
- `campaign_message` placeholder in the join form contains
  `"The {{race}} {{class}} {{name}} has joined…"` → **template syntax in a
  user-influenced field** → SSTI hypothesis is born from the UI, not a scanner.

### 🧠 Interactive Challenge

<details>
<summary><b>Challenge:</b> the join form template reads
<code>The {{race}} {{class}} {{name}} has joined…</code>. What are the two
distinct ways a user's input can reach a Handlebars render?</summary>

1. **As data** — user value passed as a context variable (escaped, literal).
2. **As template** — user value concatenated *into* the template string before
   compile (parsed → executable). Only #2 is SSTI; proving which one you have
   is the whole game.
</details>

### ❌ Failure Log — What I Tried First & Why It Failed

> Mandatory section. In real engagements ~70% of attempts fail — this
> log is what builds troubleshooting memory.

1. Assumed **port 445/80 "must be open"** and polled them before the sweep →
   **Result:** filtered/absent. *Takeaway:* port guessing wastes cycles; the
   full `-p-` sweep is the only truth.
2. `gobuster … &` / `nohup …` inside `docker exec` → **Result:** process dies
   with the exec (even twice, even after `docker exec -d`). *Takeaway:*
   background work needs `setsid`/`docker exec -d` **and** a verify step —
   silently-dead scanners look like "no findings".
3. Character POST → **403 "Invalid CSRF token"** with what looked like the
   right token → **Result:** my own bug: fresh cookie jar on each request
   (stale/blank token). *Takeaway:* reproduce the browser exactly — one jar,
   GET→POST in the same chain — before blaming the app.
4. `name={{7*7}}` → rendered **literally** → **Result:** name is *data*, not
   template. *Takeaway:* a negative result here doesn't kill SSTI; it tells
   you which field is which.
5. `message={{7*7}}` → **400** → I first read it as "braces blocked". Later
   realized Handlebars *throws a parse error* on `{{7*7}}` (invalid
   expression) → **400 = the message IS being compiled as a template.**
   *Takeaway:* an error is a distinguisher — identify *who* throws before
   filing it as a block.
6. Classic prototype-payload SSTI (`{{constructor…}}`, `lookup` chains,
   `split`/`replace`) → **Result:** blocked (Handlebars ≥4.6 protection),
   methods blocked, output HTML-escaped, `{{#each this}}` showed an **empty
   context**. *Takeaway:* string SSTI was **intentionally locked down** —
   author wants you to leave this path.
7. IDOR tests on `/character/15` (bare) → **404** → invalid test: the route is
   `/character/:id/edit`-suffixed; cross-user read/write on real URLs also
   404'd. SQLi probes → generic 400s (validated). Password spray on the
   seeded `admin@dzcampaigns.htb` → 417s, theme wordlist dry.
8. ~3 h in, surface exhausted (traversal, backups, vhosts, mass-assignment,
   XSS, spray — all dead) → **Result:** wall. *Takeaway:* at a declared wall,
   **research the box** — HTB writeups name the CVE, and you still have to
   make the PoC work yourself (see below).

### The Breakthrough (Root Cause Breakdown)

**The Flaw (phase 1 — CVE-2026-33937):** Handlebars `compile()` accepts a
*pre-built AST object* exactly like a source string. The app validates
`campaign_message` **as a string** on the normal path — but a form-encoded
body with **bracket nesting** (or a JSON body) delivers an *object*, skipping
the string parser. Inside the AST, `NumberLiteral.value` is interpolated
**raw into generated JavaScript** — so one literal's value becomes code.

**Real-World Analogy:**
> The guard checks the *envelope* ("must be a letter") — but you hand him a
> parcel shaped like an envelope whose *address label* is a script. The
> sorting machine (compiler) writes the label verbatim into its
> instructions.

**The Flaw (phase 2 — CVE-2026-58443):** Gitea's Actions PR workflow from a
fork could race the trusted-branch check — a review comment re-trigger ran
the attacker's workflow **as the runner service account** (`svc-runner`).

<details>
<summary><b>🧠 Mini-challenge:</b> the app pinned <code>handlebars 4.7.8</code>
and used <code>urlencoded({extended:false})</code>. Why did both facts matter
to the exploit?</summary>

4.7.8 = vulnerable (later versions hardened AST input), and
`extended:false` means nested keys are **not** parsed by qs — the JSON/other
delivery path had to be found empirically (nested body variants), which is
exactly what the failure log records.
</details>

## 3. Foothold (Initial Access)

### Command Breakdown

```text
Syntax structure (reusable RCE helper pattern):
rce.py "cmd"  → POST crafted /character → read /campaign/1 → decode hex chunk
```

The render path HTML-escapes output, so every command's stdout is
**hex-encoded** inside the log entry and decoded client-side — that is the
`undefined<hex>` trick in one line.

```bash
python3 rce.py 'id'        # uid=996(darkzero) — not www-data!
```

```text
POST /character  body: campaign_message = pre-built AST object
                  → compiler emits: lookup(this, 0) + <RAW JS> + …
                  → child_process.execSync(cmd) as the app user
GET  /campaign/1 → log entry holds the hex-encoded stdout
```

Payload debugging (all empirical, in order):

1. First RCE AST → **400**. Benign-number AST → **302** ⇒ *not* a validator —
   it was a **runtime error**: `process.getBuiltinModule` exists only on
   Node ≥ 22; the box runs **Node 18.19.1**.
2. Switched to `mainModule.require('child_process')` — Node-18 style.
3. Marker test `0) + "MARKER_XYZ" + (0` → rendered
   `undefinedMARKER_XYZ[object Object]` ⇒ **injection position confirmed**,
   remaining failures were shell-quoting, not the bug.

### Credentials Found

```text
.env (via RCE): DB_PASSWORD / SESSION_SECRET   (app secrets — cookie forging possible)
keytab: /etc/gitea-runner/svc-runner.keytab    (TGT minting for svc-runner later)
writeup research: josh / Rangers1              (AD user password — used for Gitea SSO)
Access Vector: HTTP (registration) → RCE; SSH creds via Gitea chain
```

### The Gitea → svc-runner chain (user flag)

```text
kinit josh  →  curl --negotiate (SPN must be HTTP/gitea.darkzero.ext — IP fails!)
            →  authenticated as darkzero-ext_josh
            →  fork DarkZero/DarkZero-Campaigns → push malicious workflow
            →  open PR → review comment → CVE-2026-58443 race
            →  act_runner executes workflow AS svc-runner
            →  workflow adds attacker SSH pubkey → ssh svc-runner@box → user.txt
```

```text
user: ~/user.txt read over SSH as svc-runner   (submitted ✓)
```

> Mid-chain the **spawn expired** and the machine was rebuilt at a new IP —
> hosts rewritten on *both* Mac and kali, fresh account registered, RCE
> re-verified, chain replayed. Respawn = new IP, always.

## 4. Privilege Escalation

### Internal Audits (order matters)

```bash
sudo -l                        # no-new-privs blocked
id; hostname                   # SRV01, app user darkzero
ls /etc/gitea-runner/          # svc-runner.keytab ← the real prize
klist -k svc-runner.keytab     # service principals (HTTP/gitea…)
```

### The Misconfiguration

- **Keytab:** `/etc/gitea-runner/svc-runner.keytab` — readable by the app user.
- **Kerberos:** `kinit -kt svc-runner.keytab svc-runner` mints a valid TGT
  without a password → LDAP/Gitea/SMB as a domain service account.
- **The `ksu` quirk:** Kerberos `ksu root` asks for root's *Kerberos*
  password — but `root` doesn't exist… **yet**. As `svc-runner` we can
  **create** the AD user `root` (GiteaMigration OU), set a password, then
  `ksu root` — Unix root on SRV01 via an AD account we own.

### Root exploitation — the AD phase (this is the Hard part)

```text
STEP  FACT                                     DECISION
1     SQL backup /root/darkzero_campaigns_      deleted-but-backed-up user =
      backup.sql holds EVERY bcrypt hash         crackable offline (hashcat 3200)
2     celia = babygurl13 (≈8 min, rules)        kinit celia → memberOf Domain Admins!
3     DCSync darkzero.ext (as celia, ON SRV01)  krbtgt + all NT hashes in hand
4     trust darkzero.ext ↔ darkzero.htb         cross-forest attack is the endgame
5     golden ticket + extra-SID =               grants Backup Operators on DC01
      InfrastructureAdministrators (nested)
6     kvno cifs/DC01…@DARKZERO.HTB              cross-realm ST (custom krb5.conf)
      → C$ listed, but Desktop = ACCESS_DENIED   SeBackup, not Admin — need intent
7     FILE_FLAG_BACKUP_SEMANTICS open → denied  srv.sys path dead; registry path alive
8     reg.py backup -o 'C:\Windows\SYSVOL\      BaseRegSaveKey (SeBackup ✓) writes
      sysvol'  → SAM/SYSTEM/SECURITY saved       hives where Authenticated Users read
9     secretsdump LOCAL → $MACHINE.ACC =        DC01$ NT/AES keys (LSA secrets!)
      DC01$ hash
10    DCSync darkzero.htb as DC01$ (aesKey)     Administrator + krbtgt of forest 2
11    PtH SMB as Administrator → root.txt       desiredAccess=0x89 (0x80 alone denied)
```

```text
root: DC01 → C:\Users\Administrator\Desktop\root.txt   (submitted ✓)
```

### 🧠 Privesc Reasoning

<details>
<summary><b>Q:</b> why did <code>reg.py backup -o C:\Windows\Temp</code> fail
with <code>ERROR_PATH_NOT_FOUND</code> while the SYSVOL path worked?</summary>

Two reasons stacked: shell quoting had eaten the backslashes
(`C:\Windows\Temp` → `C:WindowsTemp`), **and** the output must be a path the
RemoteRegistry service can write *and* we can later read. SYSVOL satisfied
both — SYSTEM can write it, every authenticated user can read it. Saving a
hive is only half the win; **plan the read-back before you save.**
</details>

## 5. Flags

> **Rule: never paste flag values into notes.** They turn the writeup
> into a flashcard (passive recognition). Record *where* the flag was
> read and *how* it was submitted — regeneration is the review.

```text
user: svc-runner@SRV01 → home directory user.txt        (submitted ✓)
root: DC01 → C:\Users\Administrator\Desktop\root.txt    (submitted ✓)
```

```bash
htb machine own <flag> -d <rating>
```

## 6. Defense & Remediation (The Sysadmin View)

| Stage | Issue | Secure Fix |
| :--- | :--- | :--- |
| Web | AST object accepted as template input | Compile only validated *strings*; reject non-string `campaign_message` at the schema layer |
| Web | Open registration + render of user fields | Rate-limit signups; keep user data strictly in the **context**, never in the template |
| CI/CD | PR workflow race (CVE-2026-58443) | Upgrade Gitea ≥ patched; never run untrusted-PR workflows with a privileged runner token |
| Secrets | Keytab readable by app user | 0600 root-only keytab; separate runner from web tier |
| AD | Deleted user's hash backed up in SQL | Purge backups or use one-way hashing exports; monitor `Domain Admin` membership changes |
| AD | Cross-forest trust without SID filtering | Quarantine/`SID filtering` on forest trusts; alert on exotic extra-SID PACs |
| OS | RemoteRegistry + SeBackup for a nested group | Restrict InfrastructureAdministrators nesting; audit `reg save` targets; deny SeBackup where unused |

## 7. Key Takeaways

1. **Metadata is a label; the scan is truth** — "Windows" machines can have a
   Linux front, and the real win starts where the front door points.
2. **String SSTI being locked down is information** — it told us the author
   disabled *exactly one* path and left the compiler itself trusting input.
3. **Every 4xx is a distinguisher** — 400-vs-403-vs-500 told parser, gate, and
   runtime apart; that ladder found the exploit faster than any scanner.
4. **A hash you can crack is a Domain Admin** — offline backups of "deleted"
   accounts are live credentials.
5. **Saving secrets is half a technique** — pick the dump location so *you*
   can read it back (SYSVOL: SYSTEM writes, everyone reads).

## 8. Methodology — Decisions & Transferable Rules

> Key Takeaways above are box-specific. This section records the
> *decision process* itself — it must outlive the box.

### Decision Tree (why each next move)

```text
STEP       FACT OBSERVED                     DECISION & WHY (vs rejected alt)
Recon      22/80 open, rest filtered         full -p- sweep; web first because nginx
           metadata=Windows, scan=Linux       redirects reveal the app (vhost)
Surface    {{race}} in join placeholder      two-path SSTI model; test WHICH field is
           open /register                     template vs data before payloads
Hypothesis proto/methods blocked, ctx empty  string SSTI locked → author intends
                                             another door; declare a wall after ladder
Research   3h wall, all surfaces dead         search the box's CVE (retired/hard boxes
                                             have writeups) — then still debug YOUR PoC
Fix        400 on AST, 302 on benign AST      runtime (Node 18 API) not validator →
                                             mainModule.require
Pivot      RCE + keytab + writeup creds       Gitea SSO (Negotiate SPN = hostname!) →
           in one enum batch                   PR race = runner as svc-runner
Privesc    deleted user in SQL backup         crack → DA → DCSync (offline beats online)
           trustAttributes=8 (no quarantine)  cross-forest extra-SID golden ticket
           Desktop ACCESS_DENIED              SeBackup intent via REGISTRY save to a
                                             share you can read, then LSA → DC01$
Escalate   DC01$ AES key in hand              DCSync forest 2 → PtH → root.txt
```

### Rules Extracted (carry to the next box)

1. **Never trust a scanner's background processes** — verify with `pgrep`;
   background inside containers needs `setsid`/`docker exec -d`.
2. **Reproduce the browser exactly (one cookie jar, one GET→POST chain)**
   before reporting CSRF/403 — 80% of my 403s were self-inflicted.
3. **Classify every error by WHO throws it** (client, parser, framework,
   runtime) — the class, not the code, tells you the next experiment.
4. **Treat "locked down" as a signpost** — when the obvious path is polished
   shut, the author left another door with a name (here: AST, then PR race).
5. **Plan exfiltration before execution** — a shell you can't read output
   from (HTML-escaped logs) forces hex; a hive you can't read back is junk.
6. **Offline cracks first:** SQL dumps, backups and registry hives beat
   online sprays — and `babygurl13`-grade passwords live in "deleted" rows.
7. **Kerberos specifics:** SPN = hostname never IP; cross-realm `kvno` needs
   the `@REALM` suffix + a custom `krb5.conf`; DCSync/tunnels die on dynamic
   RPC ports — run them **from inside** the network.
8. **Respawn protocol:** new IP → rewrite `/etc/hosts` on BOTH sides →
   re-verify with one request before replaying the chain.

## 9. 🧠 Active Recall Challenges (Before You Close This Box)

- [ ] **Challenge 1:** without rce.py, how would you read command output given
      that the log render HTML-escapes everything?
- [ ] **Challenge 2:** reproduce the AST injection locally — `npm i
      handlebars@4.7.8`, feed `compile()` an object AST with a hostile
      `NumberLiteral.value`, and show the generated JS.
- [ ] **Challenge 3:** re-run this box with zero notes — reach user in
      `<2 h>`? Root in `<4 h>`?

<details>
<summary><b>Answers</b> (attempt first, then open)</summary>

1. Hex-encode (or base64) inside the payload itself; decode client-side.
   Any encoding that survives HTML escaping works — hex was one regex away.
2.    `compile({type:'Program',body:[…]})` behaves like a compiled template;
   the `value` of a NumberLiteral lands in the generated function source
   unquoted — break out with `0)+code+(0`.
3. Targets: registration → AST test in <30 min (skip the string-SSTI wall
   once `extended:false` is seen), Gitea race scripted, then the AD ladder
   from notes' decision tree.
</details>

---

**Final Checklist (before publishing):**
- [x] Could a newcomer parse every command? (flags broken down)
- [x] Is the *WHY* of the first move explained?
- [x] Are failures documented (not just the perfect path)?
- [x] Does command order match what actually ran in the terminal?
