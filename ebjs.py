"""纯纯看番（EasyBangumi）社区 JS 源 -> Animeko 数据源。

社区仓库里的 kazumi-*.js 是“Kazumi 规则的 JS 外壳”：文件头部把 Kazumi 规则的字段
（SEARCH_URL / *_XPATH / USE_POST ...）写成常量。把这些常量还原成 Kazumi 规则，
再走和 Kazumi 一样的转换。自己手写逻辑的 JS（age、omofun、xifandm、yhw、Jellyfin……）
没有可提取的声明式配置，无法自动转换，会在报告里列出。
"""
import json
import os
import re

from convert import convert_rule

META = re.compile(r"^//\s*@(\w+)\s+(.*?)\s*$")
CONST = re.compile(r'^var\s+([A-Z][A-Z0-9_]*)\s*=\s*("(?:[^"\\]|\\.)*")\s*;\s*$')
BOOL = re.compile(r"^var\s+([A-Z][A-Z0-9_]*)\s*=\s*(true|false)\s*;\s*$")
NEED = ("SEARCH_URL", "SEARCH_LIST_XPATH", "SEARCH_NAME_XPATH", "SEARCH_RESULT_XPATH",
        "CHAPTER_ROADS_XPATH", "CHAPTER_RESULT_XPATH", "DEFAULT_BASE_URL")


def parse_extension(path):
    meta, consts = {}, {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = META.match(line)
            if m:
                meta[m.group(1)] = m.group(2)
                continue
            m = CONST.match(line)
            if m:
                try:
                    consts[m.group(1)] = json.loads(m.group(2))
                except ValueError:
                    pass
                continue
            m = BOOL.match(line)
            if m:
                consts[m.group(1)] = m.group(2) == "true"
    return meta, consts


def convert_extension(path, config=None):
    """返回 (Result, meta)。Result.source 为 None 表示无法转换。"""
    meta, c = parse_extension(path)
    label = meta.get("label") or os.path.splitext(os.path.basename(path))[0]
    from convert import Result
    res = Result(label, meta.get("versionName", ""))
    missing = [k for k in NEED if not c.get(k)]
    if missing:
        kind = "接口型" if "SEARCH_API_URL" in c else "手写 JS 逻辑"
        return res.fail("%s，没有可提取的 Kazumi 规则常量（缺 %s）" % (kind, "/".join(missing[:2]))), meta
    rule = {
        "name": label, "version": meta.get("versionName", ""),
        "baseURL": c["DEFAULT_BASE_URL"], "searchURL": c["SEARCH_URL"],
        "searchList": c["SEARCH_LIST_XPATH"], "searchName": c["SEARCH_NAME_XPATH"],
        "searchResult": c["SEARCH_RESULT_XPATH"], "chapterRoads": c["CHAPTER_ROADS_XPATH"],
        "chapterResult": c["CHAPTER_RESULT_XPATH"], "userAgent": c.get("USER_AGENT", ""),
        "referer": c.get("REFERER", ""), "usePost": bool(c.get("USE_POST")),
        "useLegacyParser": bool(c.get("USE_LEGACY_PARSER")),
    }
    res = convert_rule(rule, config)
    if res.source:
        a = res.source["arguments"]
        a["description"] = ""   # “来源”说明由 build.py 统一生成
        cover = meta.get("cover", "")
        if cover.startswith("http"):
            a["iconUrl"] = cover
    return res, meta
