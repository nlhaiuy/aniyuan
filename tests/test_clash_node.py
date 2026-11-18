"""Clash 节点 → mihomo 配置的生成自测（不需要 mihomo / 网络）。"""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan.check.clash_node import build_config, secret_values, PORT

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

# 完整的 proxies: 配置，只用第一个节点
cfg3, n3 = build_config("proxies:\n  - name: one\n    type: http\n    server: a\n    port: 1\n  - name: two\n    type: http\n    server: b\n    port: 2\n")
check("完整 proxies: 配置只取第一个节点", n3 == "one" and "server: a" in cfg3 and "server: b" not in cfg3)

for bad_in, why in (("", "空"), ("server: x", "不是从 - 开始"), ("proxies:\n", "没有节点"), ("- type: http\n  server: x\n", "没有 name")):
    try:
        build_config(bad_in); ok = False
    except ValueError:
        ok = True
    check("拒绝：%s" % why, ok)

check("日志要遮掉的值", set(secret_values(NODE)) == {"1050504963"} and "cloudnproxy.bd.com" not in secret_values(NODE))
check("密码类字段也遮", "pw" in secret_values("- name: a\n  type: http\n  username: u\n  password: pw\n") and "u" in secret_values("- name: a\n  username: u\n"))

# 命令行入口：环境变量进、配置文件出；没设置就什么都不做
with tempfile.TemporaryDirectory() as d:
    out = os.path.join(d, "m.yaml")
    env = dict(os.environ, CLASH_NODE=NODE)
    p = subprocess.run([sys.executable, "-m", "aniyuan.check.clash_node", out], env=env, capture_output=True, text=True,
                       cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    check("入口：生成配置并输出 add-mask", p.returncode == 0 and os.path.exists(out) and "::add-mask::1050504963" in p.stdout)
    check("入口：日志里没有节点原文", "cloudnproxy" not in p.stdout)
    os.remove(out)
    p = subprocess.run([sys.executable, "-m", "aniyuan.check.clash_node", out], env=dict(os.environ, CLASH_NODE=""), capture_output=True, text=True,
                       cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    check("入口：没配置就不生成", p.returncode == 0 and not os.path.exists(out))
    p = subprocess.run([sys.executable, "-m", "aniyuan.check.clash_node", out], env=dict(os.environ, CLASH_NODE="乱写的"), capture_output=True, text=True,
                       cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    check("入口：格式不对返回非 0 且不生成", p.returncode == 2 and not os.path.exists(out))
sys.exit(1 if bad else 0)
