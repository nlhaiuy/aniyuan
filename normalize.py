"""输出订阅前统一 id / 名称 / 描述的格式。

id：只做格式规整（小写、只含 a-z0-9 和连字符）。现有 id 不会被改动——id 是 Animeko 里启用状态的
    钥匙，改了用户的设置就丢了；所以这里是“新出现的 id 也必须长成这样”，而不是重命名。
名称：NFKC 规整、合并空白、括号前留一个空格；纯英文/数字的站名（如 ant、LMM）补上域名，
    写成“名称 (域名)”，和“佩可爱动漫 (peko.love)”一致。config.names 可按 id 手动指定。
描述：[警告前缀] + 站点简介 + （来源：…）。站点简介取自上游规则自带的描述，没有就写“站点 域名。”；
    来源由 build 统一生成，不再由各个转换器自己拼。
"""
import re
import unicodedata

from anx2animeko import site_host

SENTENCE_END = "。.!！?？…"
MAX_INTRO = 200
PREFIX_RE = re.compile(r"^((?:\[[^\]]*\]\s*)+)")
# 旧版转换器拼在描述里的来源说明，遇到就剥掉，避免重复
LEGACY = [
    re.compile(r"\s*（来源：[^）]*）\s*$"),   # 本程序自己生成的来源说明（manual/ 里可能放着导出的旧订阅）
    re.compile(r"\s*（(?:AniBaka 规则|Kazumi 规则)[^）]*自动转换）\s*$"),
    re.compile(r"^由(?: Kazumi 规则| 纯纯看番社区 JS 源|纯纯看番社区 JS 源)[^（]*自动转换(?:（规则更新于[^）]*）)?\s*$"),
]
ORIGIN_LABEL = {"kazumi": "Kazumi 规则", "anibaka": "AniBaka 规则", "easybangumi": "纯纯看番社区源",
                "baseline": "基线配置", "manual": "手动维护"}


def normalize_id(sid):
    """小写，只留 a-z0-9 和连字符。已经合规的 id 原样返回。"""
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", str(sid).lower())).strip("-")


def host_label(source):
    """名称里用的域名：和“同站点判断”用同一个主机名（接口源取图标域名，其余取搜索地址），去掉 www./m.。"""
    try:
        return site_host(source)
    except (KeyError, TypeError):
        return ""


def normalize_name(name, host="", override=None):
    if override:
        return override.strip()
    n = unicodedata.normalize("NFKC", str(name or ""))
    n = re.sub(r"\s+", " ", n).strip()
    n = re.sub(r"\s*\(\s*", " (", n)
    n = re.sub(r"\s*\)", ")", n)
    n = n.strip()
    # 纯英文/数字的站名（没有汉字、没有括号）：补上域名，方便在列表里分辨
    compact = n.lower().replace(" ", "")
    if host and re.fullmatch(r"[A-Za-z0-9_.\- ]+", n) and compact not in host.lower() and host.lower() not in compact:
        n = "%s (%s)" % (n, host)
    return n


def split_prefixes(desc):
    """把描述开头的 [标记] 拆出来，返回 ([标记...], 剩下的正文)。"""
    m = PREFIX_RE.match(desc or "")
    if not m:
        return [], (desc or "").strip()
    return re.findall(r"\[[^\]]*\]", m.group(1)), desc[m.end():].strip()


def clean_intro(text):
    t = text or ""   # 不做 NFKC：描述里的全角标点（！、（）等）要保留
    for rx in LEGACY:
        t = rx.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > MAX_INTRO:
        t = t[:MAX_INTRO].rstrip() + "…"
    if t and t[-1] not in SENTENCE_END:
        t += "。"
    return t


def source_note(c):
    """（来源：…）里的文字，由候选的来源/规则名/版本统一生成。"""
    origin, key, ver = c["origin"], c["key"], str(c.get("version") or "").strip()
    label = ORIGIN_LABEL.get(origin, origin)
    if origin == "manual":
        return "手动维护（manual/）"
    parts = ["%s %s" % (label, key)]
    if ver and origin != "baseline":
        parts.append(ver if not ver[0].isdigit() else "v" + ver)
    note = " ".join(parts)
    if origin in ("kazumi", "anibaka", "easybangumi") and c.get("status") not in ("override",):
        return note + "，自动转换"
    if c.get("status") == "override":
        return note + "，手写配置"
    return note


def compose_description(c, host, warn=""):
    """warn：检测失败时的警告文字（不带方括号），空表示不加。"""
    prefixes, body = split_prefixes(c["source"]["arguments"].get("description", ""))
    intro = clean_intro(body) or ("站点 %s。" % host if host else "")
    head = ("[自动检测未通过：%s]" % warn if warn else "")
    prefixes = [p for p in prefixes if not p.startswith("[自动检测未通过")]
    front = " ".join(x for x in [head] + prefixes if x)
    return (front + " " if front else "") + intro + "（来源：%s）" % source_note(c)


def normalize_source(c, source, config=None, warn=""):
    """对要输出的 source（已 strip_private 的副本）原地规整 id / name / description。"""
    config = config or {}
    a = source["arguments"]
    host = host_label(source)
    host = (config.get("site_aliases") or {}).get(host, host)   # 和合并时同一个站的规范主机名
    source["id"] = normalize_id(source["id"])
    a["name"] = normalize_name(a.get("name"), host, (config.get("names") or {}).get(source["id"]))
    a["description"] = compose_description(c, host, warn)
    return source
