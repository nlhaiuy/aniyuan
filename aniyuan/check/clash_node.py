"""把 Clash 格式的节点（Secret CLASH_NODE）转成 mihomo 的配置，供工作流起本地出口代理用。

Secret 里可以贴一个或多个节点：
  - 从 "- name: xxx" 开始的若干段（缩进随便，只要同一节点内部相对缩进正确）；
  - 或者完整的 "proxies:" 配置。
每个节点各生成一份配置（<前缀>.1.yaml、<前缀>.2.yaml ...），工作流按顺序逐个试，第一个能连通国内站的就用。
mihomo 在 127.0.0.1:PORT 起 http / socks5 混合代理，所有流量都走这个节点；aniyuan 的 ANIYUAN_PROXY 指向它即可。
不用 PyYAML（runner 上不一定有），只按文本处理。节点内容只从环境变量读，不进仓库。
"""
import os
import re
import sys

PORT = 7890
SECRET_KEYS = ("password", "uuid", "username", "token", "psk", "private-key")


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _normalize(block):
    """一个节点的原始行 -> 统一放在 "  - " 下、键在第 4 列的文本行。"""
    rest = block[1:]
    min_rest = min((_indent(l) for l in rest), default=0)
    out = ["  - " + block[0].lstrip()[2:]]
    out += ["    " + " " * max(0, _indent(l) - min_rest) + l.lstrip() for l in rest]
    return out


def _name(lines):
    for i, l in enumerate(lines):
        m = re.match(r"^\s*(?:-\s*)?name:\s*[\"']?(.+?)[\"']?\s*$", l)
        if m and (i == 0 or _indent(l) == 4):   # 只认节点自己的 name，不认嵌套里的
            return m.group(1)
    raise ValueError("节点没有 name")


def split_nodes(text):
    """返回 [(规范化后的行, 节点名), ...]，保持原来的顺序。"""
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
    blocks, cur = [], None
    for l in lines:
        if _indent(l) == base and l.lstrip().startswith("- "):
            cur = [l]
            blocks.append(cur)
        else:
            cur.append(l)
    nodes = []
    for b in blocks:
        norm = _normalize(b)
        nodes.append((norm, _name(norm)))
    return nodes


def _config(node_lines, name, port):
    quoted = name.replace("\\", "\\\\").replace('"', '\\"')
    cfg = ["mixed-port: %d" % port, "bind-address: 127.0.0.1", "allow-lan: false", "mode: rule", "log-level: warning", "ipv6: false",
           "dns:", "  enable: false", "proxies:"] + node_lines + ["rules:", '  - MATCH,"%s"' % quoted]
    return "\n".join(cfg) + "\n"


def build_configs(text, port=PORT):
    """每个节点一份完整的 mihomo 配置：[(配置文本, 节点名), ...]。"""
    return [(_config(lines, name, port), name) for lines, name in split_nodes(text)]


def secret_values(text):
    """节点里的密码 / 令牌 / X-...-Auth 之类的值，工作流用 ::add-mask:: 把它们从日志里遮掉。"""
    vals = []
    for l in text.splitlines():
        m = re.match(r"^\s*(?:-\s*)?([\w-]+):\s*[\"']?(.+?)[\"']?\s*$", l)
        if m and (m.group(1).lower() in SECRET_KEYS or m.group(1).lower().startswith("x-")):
            vals.append(m.group(2))
    return vals


def main(argv):
    """用法：python -m aniyuan.check.clash_node <输出前缀>；环境变量 CLASH_NODE 进，<前缀>.N.yaml 出；最后一行打印节点个数。"""
    text = os.environ.get("CLASH_NODE", "")
    if not text.strip():
        print(0)
        return 0
    for v in secret_values(text):
        print("::add-mask::" + v)
    try:
        cfgs = build_configs(text)
    except ValueError as e:
        print("CLASH_NODE 解析失败：%s" % e, file=sys.stderr)
        return 2
    for i, (cfg, _) in enumerate(cfgs, 1):
        open("%s.%d.yaml" % (argv[1], i), "w", encoding="utf-8").write(cfg)
    print(len(cfgs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
