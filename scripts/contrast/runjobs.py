import subprocess, sys
from concurrent.futures import ThreadPoolExecutor
jobs = [l.strip() for l in open(sys.argv[1]) if l.strip()]
P = int(sys.argv[2]) if len(sys.argv) > 2 else 13
def run(cmd):
    return subprocess.run(cmd, shell=True).returncode
with ThreadPoolExecutor(P) as ex:
    codes = list(ex.map(run, jobs))
print('done', len(codes), 'failed', sum(1 for c in codes if c))
