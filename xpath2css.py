"""把 Kazumi 规则里常见的 XPath 子集翻译成 CSS 选择器（Animeko 的 Web 数据源用 CSS）。

支持：
  //div  /div  .//a              路径步骤（. 开头视为相对当前节点）
  div[2]                         位置（翻译为 :nth-of-type(2)，通配符 * 用 :nth-child）
  [@class='a b']  [@id='x']      属性相等
  [contains(@class,'x')]         属性包含   -> [class*="x"]
  [starts-with(@id,'x')]         属性前缀   -> [id^="x"]
  [@href]                        属性存在
  末尾的 /text()                  去掉（改取元素文本，会在 notes 里提示）

不支持（抛 Unsupported，由调用方标记为需要人工处理）：
  following-sibling::  self::  |（并集）  and/or  last()  contains(text(),..)  括号分组 等
"""
import re


class Unsupported(Exception):
    pass


def _split_steps(xpath: str):
    """按 / 或 // 拆成 [(sep, step_text)]，忽略引号和中括号里的斜杠。"""
    steps = []
    i, n = 0, len(xpath)
    depth = 0
    quote = None
    cur = ""
    sep = None
    while i < n:
        ch = xpath[i]
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            cur += ch
            i += 1
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "/" and depth == 0:
            if cur or sep is not None and cur:
                steps.append((sep, cur))
            elif cur == "" and sep is not None:
                raise Unsupported("空步骤")
            if xpath.startswith("//", i):
                sep, i = "//", i + 2
            else:
                sep, i = "/", i + 1
            cur = ""
            continue
        cur += ch
        i += 1
    if cur:
        steps.append((sep, cur))
    return steps


_PRED = re.compile(r"\[(.*?)\](?=\[|$)", re.S)


def _split_predicates(step: str):
    m = re.match(r"^([^\[\]]*)(.*)$", step, re.S)
    name, rest = m.group(1).strip(), m.group(2)
    preds, depth, quote, cur = [], 0, None, ""
    for ch in rest:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
            cur += ch
            continue
        if ch == "[":
            depth += 1
            if depth == 1:
                cur = ""
                continue
        if ch == "]":
            depth -= 1
            if depth == 0:
                preds.append(cur.strip())
                cur = ""
                continue
        cur += ch
    if depth != 0 or quote:
        raise Unsupported("括号不匹配")
    return name, preds


def _css_str(v: str) -> str:
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


_P_EQ = re.compile(r"""^@([\w:-]+)\s*=\s*(['"])(.*?)\2$""")
_P_CONTAINS = re.compile(r"""^contains\(\s*@([\w:-]+)\s*,\s*(['"])(.*?)\2\s*\)$""")
_P_STARTS = re.compile(r"""^starts-with\(\s*@([\w:-]+)\s*,\s*(['"])(.*?)\2\s*\)$""")
_P_EXISTS = re.compile(r"^@([\w:-]+)$")
_P_INDEX = re.compile(r"^\d+$")


def _translate_step(name: str, preds):
    if name in ("", "."):
        raise Unsupported("空/点步骤")
    if "::" in name:
        raise Unsupported("轴 " + name)
    if name == "text()":
        raise Unsupported("text() 只能在末尾")
    if not re.match(r"^(\*|[A-Za-z][\w-]*)$", name):
        raise Unsupported("节点测试 " + name)
    css = "" if name == "*" else name
    nth = None
    for p in preds:
        if _P_INDEX.match(p):
            nth = int(p)
            continue
        m = _P_EQ.match(p)
        if m:
            css += "[%s=%s]" % (m.group(1), _css_str(m.group(3)))
            continue
        m = _P_CONTAINS.match(p)
        if m:
            css += "[%s*=%s]" % (m.group(1), _css_str(m.group(3)))
            continue
        m = _P_STARTS.match(p)
        if m:
            css += "[%s^=%s]" % (m.group(1), _css_str(m.group(3)))
            continue
        m = _P_EXISTS.match(p)
        if m:
            css += "[%s]" % m.group(1)
            continue
        raise Unsupported("谓词 [" + p + "]")
    if nth is not None:
        if nth < 1:
            raise Unsupported("位置 < 1")
        css += (":nth-child(%d)" if name == "*" else ":nth-of-type(%d)") % nth
    if not css:
        css = "*"
    return css


def xpath_to_css(xpath: str):
    """返回 (css, notes)。notes 是需要提醒的近似转换。"""
    xp = (xpath or "").strip()
    notes = []
    if not xp:
        raise Unsupported("空 XPath")
    if "|" in _strip_quotes(xp):
        raise Unsupported("并集 |")
    if re.search(r"\b(and|or)\b", _strip_quotes(xp)):
        raise Unsupported("and/or")
    if xp.startswith("."):
        xp = xp[1:]
    if xp.startswith("("):
        raise Unsupported("括号分组")
    steps = _split_steps(xp)
    if not steps:
        raise Unsupported("没有步骤")
    # 末尾 text()
    if steps and steps[-1][1].strip() == "text()":
        steps.pop()
        notes.append("末尾 text() 已改为取元素全部文本")
        if not steps:
            raise Unsupported("只有 text()")
    out = []
    for idx, (sep, step) in enumerate(steps):
        name, preds = _split_predicates(step)
        part = _translate_step(name, preds)
        if idx == 0:
            out.append(part)
        else:
            out.append((" > " if sep == "/" else " ") + part)
    return "".join(out), notes


def _strip_quotes(s: str) -> str:
    return re.sub(r"""(['"]).*?\1""", "''", s)


def join_relative(base_css: str, rel_css: str) -> str:
    """item 选择器 + 相对路径（后代）。"""
    return base_css + " " + rel_css
