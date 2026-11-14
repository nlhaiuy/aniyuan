"""和上一次订阅比的变化：新增 / 移除 / 档位 / 域名。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan import changes

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

def web(i, name, host, tier=4, factory="web-selector"):
    return {"id": i, "factoryId": factory, "arguments": {"name": name, "tier": tier, "searchConfig": {"searchUrl": "https://%s/s?q={keyword}" % host}}}

def api(i, name, host, tier=4):
    return {"id": i, "factoryId": "json-api", "arguments": {"name": name, "tier": tier, "searchConfig": {"baseUrl": "https://%s" % host, "search": {"request": {"url": "https://%s/x" % host}}}}}

old = [web("a", "甲", "a.com", 1), web("b", "乙", "b.com", 2), web("c", "丙", "c.com"), api("d", "丁", "d.com")]
new = [web("a", "甲", "a.com", 3), web("c", "丙", "c2.com"), web("e", "戊", "e.com"), api("d", "丁", "d.com")]
d = changes.diff(old, new)
check("新增", [r[0] for r in d["added"]] == ["e"])
check("移除", [r[0] for r in d["removed"]] == ["b"])
check("档位变化", d["tier"] == [("a", "甲", 1, 3)])
check("换域名", d["host"] == [("c", "丙", "c.com", "c2.com")])
check("没变的不出现", all("d" not in [r[0] for r in d[k]] for k in d))
check("json-api 源也按 baseUrl 取域名", changes.host_of(api("x", "x", "z.com")) == "z.com")
check("摘要", changes.summary(d, 4) == "新增 1、移除 1、档位变化 1、换域名 1；共 4 个源")
sec = "\n".join(changes.section(d))
check("报告里列出各类变化", "## 本次变化" in sec and "戊（e，e.com）" in sec and "甲：1 → 3" in sec and "丙：c.com → c2.com" in sec)

same = changes.diff(old, old)
check("没有变化", changes.is_empty(same) and "没有变化" in "\n".join(changes.section(same)) and "没有变化" in changes.summary(same, 4))

many = changes.diff([], [web("i%d" % i, "n%d" % i, "h.com") for i in range(50)])
sec = changes.section(many)
check("太多时截断并写明还有多少", sum(1 for l in sec if l.startswith("- n")) == changes.LIMIT and any("还有 10 条" in l for l in sec))
sys.exit(1 if bad else 0)
