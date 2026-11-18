"""Clash 节点 → mihomo 配置的生成自测（不需要 mihomo / 网络）。"""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan.check.clash_node import build_configs, split_nodes, secret_values, PORT

def build_config(text):
    return build_configs(text)[0]

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

NODE = """- name: bd直连
    server: cloudnproxy.bd.com
    type: http
    port: 443
    udp: false
    skip-cert-verify: true
    headers:
      Host: cloudnproxy.bd.com
      X-T5-Auth: 1050504963
      User-Agent: ""
"""
cfg, name = build_config(NODE)
check("节点名取出来了", name == "bd直连")
check("混合代理只监听本机", "mixed-port: %d" % PORT in cfg and "bind-address: 127.0.0.1" in cfg and "allow-lan: false" in cfg)
check("所有流量走这个节点", cfg.rstrip().endswith('- MATCH,"bd直连"'))
check("节点内容原样保留（含嵌套的 headers）", "    server: cloudnproxy.bd.com\n" in cfg and "    headers:\n      Host: cloudnproxy.bd.com\n      X-T5-Auth: 1050504963\n" in cfg
      and '      User-Agent: ""\n' in cfg)
check("节点在 proxies: 下、缩进统一", "proxies:\n  - name: bd直连\n    server:" in cfg)

# 首行被去掉缩进、其余行缩进更深（从聊天里复制粘贴常见的样子）
cfg2, _ = build_config("  - name: a\n      server: s\n      type: http\n      port: 1\n      headers:\n        K: v\n")
check("缩进不规整也能规范化", "    server: s\n" in cfg2 and "    headers:\n      K: v\n" in cfg2)

# 多个节点：每个节点一份配置，顺序不变
TWO = "proxies:\n  - name: one\n    type: http\n    server: a\n    port: 1\n  - name: two\n    type: socks5\n    server: b\n    port: 2\n    headers:\n      K: v\n"
many = build_configs(TWO)
check("多个节点各出一份配置、顺序不变", [n for _, n in many] == ["one", "two"])
check("每份配置只含自己的节点", "server: a" in many[0][0] and "server: b" not in many[0][0] and "server: b" in many[1][0] and "server: a" not in many[1][0])
check("每份配置都把流量指向自己的节点", many[0][0].rstrip().endswith('- MATCH,"one"') and many[1][0].rstrip().endswith('- MATCH,"two"'))
check("不带 proxies: 的多节点（缩进不同）也行", [n for _, n in build_configs("- name: x\n    type: http\n    server: a\n    port: 1\n- name: y\n    type: http\n    server: b\n    port: 2\n")] == ["x", "y"])
check("嵌套里的 name 不会被当成节点名", split_nodes("- type: http\n  name: real\n  headers:\n    name: fake\n  server: s\n  port: 1\n")[0][1] == "real")

for bad_in, why in (("", "空"), ("server: x", "不是从 - 开始"), ("proxies:\n", "没有节点"), ("- type: http\n  server: x\n", "没有 name")):
    try:
        build_config(bad_in); ok = False
    except ValueError:
        ok = True
    check("拒绝：%s" % why, ok)

check("日志要遮掉的值", set(secret_values(NODE)) == {"1050504963"} and "cloudnproxy.bd.com" not in secret_values(NODE))
check("密码类字段也遮", "pw" in secret_values("- name: a\n  type: http\n  username: u\n  password: pw\n") and "u" in secret_values("- name: a\n  username: u\n"))

# 命令行入口：环境变量进、<前缀>.N.yaml 出、最后一行是节点个数；没设置就输出 0
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def run(env_val, prefix):
    return subprocess.run([sys.executable, "-m", "aniyuan.check.clash_node", prefix], env=dict(os.environ, CLASH_NODE=env_val), capture_output=True, text=True, cwd=ROOT)
with tempfile.TemporaryDirectory() as d:
    pre = os.path.join(d, "m")
    p = run(NODE + "- name: one\n    type: http\n    server: a\n    port: 1\n- name: two\n    type: socks5\n    server: b\n    port: 2\n", pre)
    check("入口：生成配置并输出 add-mask 和个数", p.returncode == 0 and "::add-mask::1050504963" in p.stdout and p.stdout.strip().splitlines()[-1] == "3"
          and all(os.path.exists("%s.%d.yaml" % (pre, i)) for i in (1, 2, 3)))
    check("入口：日志里没有节点原文", "cloudnproxy" not in p.stdout)
    for i in (1, 2, 3):
        os.remove("%s.%d.yaml" % (pre, i))
    p = run("", pre)
    check("入口：没配置就输出 0、不生成", p.returncode == 0 and p.stdout.strip() == "0" and not os.path.exists(pre + ".1.yaml"))
    p = run("乱写的", pre)
    check("入口：格式不对返回非 0 且不生成", p.returncode == 2 and not os.path.exists(pre + ".1.yaml"))
sys.exit(1 if bad else 0)
