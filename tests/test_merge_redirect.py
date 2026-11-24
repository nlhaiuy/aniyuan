"""同一个站只有一部分候选因域名跳转换了新域名时，不能被拆成两组（否则输出重复 id，整个构建失败）。
真实发生过：akianime.cc → akianime.com、baimao 同类，报 AssertionError: 出现重复 id。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan.build import merge
from aniyuan.normalize import normalize_id

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

def cand(origin, key, host, date, status="ok", orig=None, play="ok"):
    sid = {"kazumi": "kazumi-", "anibaka": "anibaka-", "easybangumi": "kazumi-"}[origin] + key
    c = dict(origin=origin, key=key, date=date, notes=[], smoke={"status": status, "play": play},
             source={"id": sid, "factoryId": "web-selector", "version": 2,
                     "arguments": {"name": key, "iconUrl": "", "searchConfig": {"searchUrl": "https://%s/s?wd={keyword}" % host}}})
    if orig:
        c["orig_site"] = orig
    return c

def ids(chosen):
    return sorted(normalize_id(c["source"]["id"]) for c in chosen)

# 1. 真实场景：anibaka 被检测改写到新域名，kazumi 还在旧域名
cs = [cand("anibaka", "akianime", "akianime.com", 300, orig="akianime.cc"),
      cand("kazumi", "akianime", "akianime.cc", 100, orig="akianime.cc")]
ch, dec = merge(cs, {})
check("一部分候选换了新域名：仍是同一个站，只选出一个", len(ch) == 1 and len(dec) == 1 and len(dec[0]["members"]) == 2)
check("输出 id 不重复", len(ids(ch)) == len(set(ids(ch))))

# 2. 没记录原始站点（老数据 / 没联网检测）：靠兜底合并，不报错
cs = [cand("anibaka", "baimao", "baimaodm.com", 300, status="blocked"),
      cand("kazumi", "baimao", "bmddm.com", 100, status="ok")]
ch, dec = merge(cs, {})
check("兜底：同名撞 id 时合并成一个，不让构建失败", len(ch) == 1 and len(set(ids(ch))) == 1)
check("兜底：保留检测结果更好的（通过 > 没结论）", ch[0]["origin"] == "kazumi")
check("兜底：取舍记录里写明合并了，成员都在", "已合并为一个" in dec[0]["reason"] and len(dec[0]["members"]) == 2 and len(dec) == 1)
check("兜底：落选的候选不再标记为入选", sum(1 for c in cs if c.get("chosen")) == 1)

# 3. 兜底在两边检测结果一样时按修改时间
cs = [cand("anibaka", "x", "a.com", 100), cand("kazumi", "x", "b.com", 300)]
ch, _ = merge(cs, {})
check("兜底：检测结果一样取更新的", len(ch) == 1 and ch[0]["origin"] == "kazumi")

# 4. 不相关的站点不受影响
cs = [cand("anibaka", "a1", "a1.com", 1), cand("kazumi", "b2", "b2.com", 1), cand("easybangumi", "c3", "c3.com", 1),
      cand("anibaka", "d4", "d4.net", 1, orig="d4.com")]
ch, dec = merge(cs, {})
check("不相关的站点各自保留", len(ch) == 4 and len(set(ids(ch))) == 4)
check("原始域名相同才算同一站：改过域名的 d4 不会吞掉别人", sorted(c["key"] for c in ch) == ["a1", "b2", "c3", "d4"])

# 5. 域名别名仍然生效，原始域名也走别名
cs = [cand("anibaka", "z", "new.com", 2, orig="old.com"), cand("kazumi", "z", "alias-of-old.com", 1)]
ch, _ = merge(cs, {"site_aliases": {"alias-of-old.com": "old.com"}})
check("site_aliases 对原始域名同样生效", len(ch) == 1)
sys.exit(1 if bad else 0)
