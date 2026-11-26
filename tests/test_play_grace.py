"""播放宽限（play_none_grace）的自测（不联网）：以前能播、偶尔一次没抓到视频，不立刻降档。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan.check.health import update_health, auto_tier

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


def cand(play):
    src = {"id": "x", "factoryId": "web-selector", "version": 2, "arguments": {"name": "a", "searchConfig": {"searchUrl": "https://a.com/s?wd={keyword}"}, "iconUrl": ""}}
    return dict(origin="kazumi", key="a", source=src, date=1, notes=[], smoke={"status": "ok", "reason": "x", "play": play})


def feed(plays, hist=None, grace=3):
    hist, c = dict(hist or {}), None
    for i, p in enumerate(plays):
        c = cand(p)
        hist = update_health([c], hist, 100 + i, 2, 14, grace)
    return c, hist


c, h = feed(["ok", "none"])
check("以前能播、这次 none（1/3）：按能播算，第 1 档", c["smoke"]["play"] == "ok" and auto_tier(c)[0] == 1 and c["smoke"]["play_raw"] == "none")
check("宽限期内历史里仍记为能播", h["kazumi:a"]["play"] == "ok" and h["kazumi:a"]["play_none"] == 1)
check("宽限期内备注里写明", any("连续 1/3" in n for n in c["notes"]))
c, _ = feed(["ok", "none", "none"])
check("连续 2 次 none（2/3）：仍按能播", c["smoke"]["play"] == "ok")
c, h = feed(["ok", "none", "none", "none"])
check("连续 3 次 none：真的降到第 2 档", c["smoke"]["play"] == "none" and auto_tier(c)[0] == 2 and h["kazumi:a"]["play"] == "none")
c, _ = feed(["ok", "none", "ok", "none", "none"])
check("中间又能播一次：计数清零，不降档", c["smoke"]["play"] == "ok")
c, _ = feed(["none", "none"])
check("从没能播过的：不适用宽限，直接 none", c["smoke"]["play"] == "none" and auto_tier(c)[0] == 2)
c, _ = feed(["ok", "mismatch"])
check("mismatch（认不出视频地址）不在宽限内：直接降档", c["smoke"]["play"] == "mismatch" and auto_tier(c)[0] == 3)
c, _ = feed(["ok", "blocked"])
check("blocked（验证码）不在宽限内", c["smoke"]["play"] == "blocked")
c, _ = feed(["ok", "none"], grace=0)
check("play_none_grace=0：关闭", c["smoke"]["play"] == "none")

print("\n全部通过" if not bad else "\n%d 项失败" % bad)
sys.exit(1 if bad else 0)
