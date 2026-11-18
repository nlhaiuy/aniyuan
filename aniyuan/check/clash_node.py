"""把 Clash 格式的节点（Secret CLASH_NODE）转成 mihomo 的完整配置，供工作流起本地代理用。

Secret 里可以直接贴：
  - 单个节点：从 "- name: xxx" 开始的那一段（缩进随便，只要同一节点内部相对缩进正确）；
  - 或者完整的 "proxies:" 配置（第一个节点会被用作出口）。
mihomo 在 127.0.0.1:PORT 起一个 http/socks5 混合代理，所有流量都走这个节点；aniyuan 的 ANIYUAN_PROXY 指向它即可。
不用 PyYAML（runner 上不一定有），只按文本处理。节点内容只从环境变量读，不进仓库。
"""
import os
import re
import sys

PORT = 7890
SECRET_KEYS = ("password", "uuid", "username", "token", "psk", "private-key")


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _node_block(text):
    """取出 proxies 下的第一个节点，规范成 4 空格缩进的 "  - name: ..." 文本块。返回 (行列表, 节点名)。"""
    lines = [l.rstrip() for l in text.replace("\t", "    ").splitlines() if l.strip() and not l.strip().startswith("#")]
    if not lines:
        raise ValueError("CLASH_NODE 是空的")
    if lines[0].strip() == "proxies:":
        lines = lines[1:]
        if not lines:
            raise ValueError("proxies: 下面没有节点")
    if not lines[0].lstrip().startswith("- "):
        raise ValueError("节点要从 \"- name: ...\" 开始")
    base = _indent(lines[0])
    block = [lines[0]]
    for l in lines[1:]:
        if _indent(l) <= base and l.lstrip().startswith("- "):
            break   # 下一个节点，只用第一个
        block.append(l)
    first_key_col = base + 2                                   # "- " 之后第一个键所在的列
    rest = block[1:]
    min_rest = min((_indent(l) for l in rest), default=first_key_col)
    out = ["  - " + block[0].lstrip()[2:]]                    # 节点统一放在 "  - " 下，键在第 4 列
    for l in rest:
        out.append("    " + " " * max(0, _indent(l) - min_rest) + l.lstrip())
    m = re.search(r"^\s*(?:-\s*)?name:\s*[\"']?(.+?)[\"']?\s*$", out[0].replace("  - ", "  - ", 1), re.M)
    if not m:
        for l in out:
            m = re.match(r"^\s*name:\s*[\"']?(.+?)[\"']?\s*$", l)
            if m:
                break
    if not m:
        raise ValueError("节点没有 name")
    return out, m.group(1)


def build_config(text, port=PORT):
    out, name = _node_block(text)
    quoted = name.replace("\\", "\\\\").replace('"', '\\"')
    cfg = ["mixed-port: %d" % port, "bind-address: 127.0.0.1", "allow-lan: false", "mode: rule", "log-level: warning", "ipv6: false",
           "dns:", "  enable: false", "proxies:"] + out + ["rules:", '  - MATCH,"%s"' % quoted]
    return "\n".join(cfg) + "\n", name


def secret_values(text):
    """节点里的密码 / 令牌 / X-...-Auth 之类的值，工作流用 ::add-mask:: 把它们从日志里遮掉。"""
    vals = []
    for l in text.splitlines():
        m = re.match(r"^\s*(?:-\s*)?([\w-]+):\s*[\"']?(.+?)[\"']?\s*$", l)
        if m and (m.group(1).lower() in SECRET_KEYS or m.group(1).lower().startswith("x-")):
            vals.append(m.group(2))
    return vals


def main(argv):
    text = os.environ.get("CLASH_NODE", "")
    if not text.strip():
        return 0
    for v in secret_values(text):
        print("::add-mask::" + v)
    try:
        cfg, name = build_config(text)
    except ValueError as e:
        print("CLASH_NODE 解析失败：%s" % e, file=sys.stderr)
        return 2
    open(argv[1], "w", encoding="utf-8").write(cfg)
    print("节点配置已生成（%d 行）" % cfg.count("\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
