"""检测历史：连续失败才降级的自测（不联网）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan.build import merge
from aniyuan.check.health import update_health, confirmed_fail

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

# ---- 自动分档（tier）----
from aniyuan.check.health import auto_tier
from aniyuan.build import apply_auto_tier


def tcand(status=None, play=None, grace=None, play_hist=None, guess=False, origin="anibaka", key="k", tier=4, name="n"):
    c = cand(origin, key, "t.com", 1, "id-" + key, status, play)
    c["source"]["arguments"]["tier"] = tier
    c["source"]["arguments"]["name"] = name
    if grace is not None:
        c["health"] = {"grace": grace, "play": play_hist}
    if guess:
        c["guess"] = True
    return c


check("通过 + 能播 -> 1", auto_tier(tcand("ok", "ok"))[0] == 1)
check("通过 + 没跑播放检测 -> 2", auto_tier(tcand("ok"))[0] == 2)
check("通过 + 没抓到视频 -> 2", auto_tier(tcand("ok", "none"))[0] == 2)
check("通过 + 认不出视频地址 -> 3", auto_tier(tcand("ok", "mismatch"))[0] == 3)
check("明确失败（已过宽限期）-> 4", auto_tier(tcand("fail", grace=False))[0] == 4)
check("宽限期内按上次通过时的播放成绩", auto_tier(tcand("fail", grace=True, play_hist="ok"))[0] == 1)
check("无法访问（没有结论）-> 3", auto_tier(tcand("unreachable"))[0] == 3 and auto_tier(tcand("blocked"))[0] == 3)
check("推测的搜索地址且没结论 -> 4", auto_tier(tcand("unreachable", guess=True))[0] == 4)
check("没有检测结果 -> None", auto_tier(tcand())[0] is None)

cs = [tcand("ok", "ok", key="a"), tcand("ok", "ok", key="b", tier=2),
      tcand("ok", "ok", key="d"), tcand("ok", "ok", key="e", name="E名"), tcand(key="f")]
apply_auto_tier(cs, {"tiers": {"d": 3, "E名": 0}})
t = {c["key"]: c["source"]["arguments"]["tier"] for c in cs}
check("默认值的源按检测结果自动分档", t["a"] == 1)
check("手调过的（tier 不是默认值）不动", t["b"] == 2)
check("config.tiers 点名的不动（按 key 或名称）", t["d"] == 4 and t["e"] == 4)
check("没有检测结果的保持默认", t["f"] == 4)
check("自动分档写进备注", any("优先级自动设为 1" in n for n in cs[0]["notes"]))
cs = [tcand("ok", "ok", key="a")]
apply_auto_tier(cs, {"auto_tier": False})
check("auto_tier=false 关闭", cs[0]["source"]["arguments"]["tier"] == 4)
sys.exit(1 if bad else 0)
