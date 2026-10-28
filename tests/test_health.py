"""检测历史：连续失败才降级的自测（不联网）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from build import merge
from health import update_health, confirmed_fail

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


def cand(origin, key, host, date, sid, status=None, play=None):
    src = {"id": sid, "factoryId": "web-selector", "version": 2,
           "arguments": {"name": key, "searchConfig": {"searchUrl": "https://%s/s?wd={keyword}" % host}, "iconUrl": ""}}
    c = dict(origin=origin, key=key, source=src, date=date, notes=[])
    if status:
        c["smoke"] = {"status": status, "reason": "x"}
        if play:
            c["smoke"]["play"] = play
    return c


def run(c, hist, now=100, threshold=2):
    return update_health([c], hist, now, threshold)


# 以前通过过，这次第一次 fail -> 宽限期
h = run(cand("anibaka", "a", "t.com", 1, "anibaka-a", "ok", "ok"), {}, 100)
check("通过：fails 清零并记录 last_ok 和播放结果", h["anibaka:a"]["fails"] == 0 and h["anibaka:a"]["last_ok"] == 100 and h["anibaka:a"]["play"] == "ok")
c = cand("anibaka", "a", "t.com", 1, "anibaka-a", "fail")
h2 = run(c, h, 200)
check("以前通过过、第一次 fail：宽限期", c["health"]["grace"] and h2["anibaka:a"]["fails"] == 1 and not confirmed_fail(c))
check("宽限期会在备注里说明", any("暂不降级" in n for n in c["notes"]))
c = cand("anibaka", "a", "t.com", 1, "anibaka-a", "fail")
h3 = run(c, h2, 300)
check("连续第 2 次 fail：到阈值，真正降级", not c["health"]["grace"] and h3["anibaka:a"]["fails"] == 2 and confirmed_fail(c))
c = cand("anibaka", "a", "t.com", 1, "anibaka-a", "ok")
h4 = run(c, h3, 400)
check("再通过一次：fails 清零", h4["anibaka:a"]["fails"] == 0)
c = cand("anibaka", "n", "n.com", 1, "anibaka-n", "fail")
h5 = run(c, {}, 100)
check("从没通过过：第一次 fail 就算数", not c["health"]["grace"] and confirmed_fail(c))

# 没有结论的状态：不算失败，也不清零
c = cand("anibaka", "a", "t.com", 1, "anibaka-a", "unreachable")
h6 = run(c, h2, 500)
check("unreachable/blocked 不改变失败计数", h6["anibaka:a"]["fails"] == 1 and h6["anibaka:a"]["last_ok"] == 100 and not c["health"]["grace"])
c = cand("anibaka", "a", "t.com", 1, "anibaka-a")
h7 = run(c, h2, 600)
check("没检测的候选：记录原样保留", h7["anibaka:a"]["fails"] == 1)
check("阈值可配置", run(cand("anibaka", "a", "t.com", 1, "anibaka-a", "fail"), h, 700, 1)["anibaka:a"]["fails"] == 1
      and not (lambda c: (run(c, h, 700, 1), c["health"]["grace"])[1])(cand("anibaka", "a", "t.com", 1, "anibaka-a", "fail")))
check("这次没出现的候选不保留", "anibaka:a" not in update_health([], h, 800))

# 合并：最新的偶发 fail，不应该立刻换成旧来源
def pair(new_status, hist):
    new = cand("anibaka", "a", "t.com", 200, "anibaka-a", new_status)
    old = cand("kazumi", "A", "t.com", 100, "kazumi-a", "ok", "ok")
    update_health([new, old], hist, 900)
    return merge([new, old], {})

hist_ok = {"anibaka:a": {"fails": 0, "last_ok": 100, "play": "ok"}}
ch, d = pair("fail", hist_ok)
check("最新的第一次 fail、以前通过过：仍用最新的", ch[0]["origin"] == "anibaka" and "暂不降级" in d[0]["reason"])
ch, d = pair("fail", {"anibaka:a": {"fails": 1, "last_ok": 100, "play": "ok"}})
check("最新的连续第 2 次 fail：改用通过的旧来源", ch[0]["origin"] == "kazumi")
ch, d = pair("fail", {})
check("最新的从没通过过：第一次 fail 就改用通过的", ch[0]["origin"] == "kazumi")
# 宽限期按上次的播放成绩排名：上次没抓到视频（none），而旧来源能播 -> 旧来源胜
ch, d = pair("fail", {"anibaka:a": {"fails": 0, "last_ok": 100, "play": "none"}})
check("宽限期按上次播放成绩排名", ch[0]["origin"] == "kazumi")
sys.exit(1 if bad else 0)
