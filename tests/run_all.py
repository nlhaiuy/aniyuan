#!/usr/bin/env python3
"""自动发现 tests/test_*.py 并并行运行。新增测试文件不用再改工作流清单。

用法: python tests/run_all.py [-j N] [名字片段 ...]
  - 每个测试是独立进程（互不影响，用的都是临时目录 / 临时端口）。
  - 失败的测试会在最后打印完整输出；任何一个失败退出码就是 1。
  - 环境变量 KAZUMI_RULES 原样传给子进程（test_xpath2css 用）。
"""
import argparse
import glob
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
TIMEOUT = 600


def run(path):
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-I", path], capture_output=True, text=True,
                           timeout=TIMEOUT, cwd=os.path.dirname(HERE))
        rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        rc, out = 124, "超时（%d 秒）\n%s" % (TIMEOUT, (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""))
    return os.path.basename(path)[:-3], rc, out, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-j", type=int, default=min(4, os.cpu_count() or 2))
    ap.add_argument("only", nargs="*", help="只跑名字里含这些片段的测试")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(HERE, "test_*.py")))
    if a.only:
        files = [f for f in files if any(s in os.path.basename(f) for s in a.only)]
    if not files:
        print("没有匹配的测试"); return 1
    failed = []
    with ThreadPoolExecutor(max_workers=max(1, a.j)) as ex:
        for name, rc, out, secs in ex.map(run, files):
            print("%s %-28s %5.1fs" % ("PASS" if rc == 0 else "FAIL", name, secs), flush=True)
            if rc != 0:
                failed.append((name, out))
    for name, out in failed:
        print("\n===== %s 输出 =====\n%s" % (name, out.rstrip()))
    print("\n%d 个测试，%d 个失败" % (len(files), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
