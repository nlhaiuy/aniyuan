"""id / 名称 / 描述规范化的自测（不联网）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from normalize import (clean_intro, compose_description, normalize_id, normalize_name, normalize_source,
                       source_note, split_prefixes)

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


def cand(origin, key, version, desc, status="ok", host="x.com"):
    src = {"id": "anibaka-x", "factoryId": "web-selector", "version": 2,
           "arguments": {"name": "N", "description": desc, "iconUrl": "",
                         "searchConfig": {"searchUrl": "https://%s/s?wd={keyword}" % host}}}
    return dict(origin=origin, key=key, version=version, status=status, source=src, notes=[])


# ---- id：合规的原样不动，不合规的规整 ----
for sid in ("anibaka-2kdm", "anibaka-ani-pekolove", "kazumi-xfdmnext", "kazumi-9ciyuan"):
    check("现有 id 不变：%s" % sid, normalize_id(sid) == sid)
check("大写和下划线规整", normalize_id("Anibaka-Ani_Peko Love") == "anibaka-ani-peko-love")
check("连续连字符合并、首尾去掉", normalize_id("-kazumi--x-") == "kazumi-x")

# ---- 名称 ----
check("纯英文站名补域名", normalize_name("mutefun", "mutedm.com") == "mutefun (mutedm.com)")
check("含汉字的不补域名", normalize_name("路漫漫动漫", "lm6.net") == "路漫漫动漫")
check("已经带括号的不重复补", normalize_name("五弹幕 (5DM)", "5dm.dev") == "五弹幕 (5DM)")
check("全角括号转半角、括号前留一个空格", normalize_name("佩可爱动漫（peko.love）", "x.com") == "佩可爱动漫 (peko.love)")
check("合并多余空白", normalize_name("  A  B　C ", "") == "A B C")
check("名称里已有域名不重复补", normalize_name("ylys.cc", "ylys.cc") == "ylys.cc")
check("名称就是域名里的名字：不补", normalize_name("mgnacg", "mgnacg.com") == "mgnacg" and normalize_name("omofun03", "omofun03.top") == "omofun03")
check("config.names 手动指定优先", normalize_name("ant", "mayi520.org", "蚂蚁动漫") == "蚂蚁动漫")
check("幂等", normalize_name(normalize_name("ant", "mayi520.org"), "mayi520.org") == "ant (mayi520.org)")

# ---- 描述 ----
check("拆出开头的 [标记]", split_prefixes("[a] [b] 正文") == (["[a]", "[b]"], "正文"))
check("没有标记", split_prefixes("正文") == ([], "正文"))
check("简介补句号、合并空白", clean_intro("  动漫  源\n简介 ") == "动漫 源 简介。")
check("已有句末标点不重复", clean_intro("好用！") == "好用！")
check("剥掉旧版 AniBaka 来源后缀", clean_intro("简介。 （AniBaka 规则 age rev 6 自动转换）") == "简介。")
check("剥掉旧版整句来源说明", clean_intro("由 Kazumi 规则 mutefun v1.4 自动转换") == "")
check("剥掉旧版纯纯看番来源说明", clean_intro("由纯纯看番社区 JS 源 kazumi.7sefun v1.2.1 自动转换") == "")
check("过长的简介截断", len(clean_intro("长" * 500)) <= 202)

check("来源：AniBaka", source_note(cand("anibaka", "age", "rev 6", "")) == "AniBaka 规则 age rev 6，自动转换")
check("来源：Kazumi 版本加 v", source_note(cand("kazumi", "mutefun", "1.4", "")) == "Kazumi 规则 mutefun v1.4，自动转换")
check("来源：纯纯看番", source_note(cand("easybangumi", "kazumi-7sefun", "1.2.1", "")) == "纯纯看番社区源 kazumi-7sefun v1.2.1，自动转换")
check("来源：手写配置", source_note(cand("kazumi", "xfdmnext", "1.0", "", status="override")) == "Kazumi 规则 xfdmnext v1.0，手写配置")
check("来源：基线", source_note(cand("baseline", "age", "rev 6", "")) == "基线配置 age")
check("来源：手动", source_note(cand("manual", "anibaka-girigirilove", "", "")) == "手动维护（manual/）")

c = cand("anibaka", "age", "rev 6", "AGE动漫视频源 （AniBaka 规则 age rev 6 自动转换）", host="www.agedm.io")
check("完整描述", compose_description(c, "agedm.io") == "AGE动漫视频源。（来源：AniBaka 规则 age rev 6，自动转换）")
c = cand("kazumi", "mutefun", "1.4", "")
check("没有简介：写站点域名", compose_description(c, "mutedm.com") == "站点 mutedm.com。（来源：Kazumi 规则 mutefun v1.4，自动转换）")
c = cand("anibaka", "age", "rev 6", "[选择器已自动修复] 简介")
check("保留其他 [标记] 在最前", compose_description(c, "x.com").startswith("[选择器已自动修复] 简介。"))
d = compose_description(c, "x.com", "HTTP 404")
check("警告在最前、不重复", d.startswith("[自动检测未通过：HTTP 404] [选择器已自动修复]") and d.count("自动检测未通过") == 1)
c = cand("anibaka", "age", "rev 6", "[自动检测未通过：旧] 简介")
check("旧警告不会残留（这次没警告就去掉）", "自动检测未通过" not in compose_description(c, "x.com"))
d1 = compose_description(c, "x.com", "HTTP 404")
c2 = cand("anibaka", "age", "rev 6", d1)
check("描述规整两遍结果不变（幂等）", compose_description(c2, "x.com", "HTTP 404") == d1)

# ---- 整体 ----
c = cand("kazumi", "LMM", "2.3", "")
c["source"]["id"] = "Kazumi-LMM"; c["source"]["arguments"]["name"] = "LMM"
s = normalize_source(c, c["source"], {}, "")
check("normalize_source：id / 名称 / 描述", s["id"] == "kazumi-lmm" and s["arguments"]["name"] == "LMM (x.com)"
      and s["arguments"]["description"] == "站点 x.com。（来源：Kazumi 规则 LMM v2.3，自动转换）")
c = cand("manual", "anibaka-girigirilove", "", "", host="m3u8.girigirilove.com")
s = normalize_source(c, c["source"], {"site_aliases": {"m3u8.girigirilove.com": "ani.girigirilove.com"}}, "")
check("站点别名：描述里用规范主机名", "站点 ani.girigirilove.com。" in s["arguments"]["description"])
sys.exit(1 if bad else 0)
