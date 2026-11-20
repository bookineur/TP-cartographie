import subprocess, sys
m = dict(l.split() for l in open(sys.argv[1]))
for l in subprocess.run(["git", "ls-files", "-s"], capture_output=True, text=True).stdout.splitlines():
    meta, path = l.split("\t", 1)
    mode, sha, _ = meta.split()
    if sha in m:
        subprocess.run(["git", "update-index", "--cacheinfo", f"{mode},{m[sha]},{path}"], check=True)
