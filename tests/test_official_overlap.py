"""与官方订阅互补：同一个站官方已有时，自有源降档 / 剔除；官方失效时自有源保留补位；没结论绝不剔除。"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan import official

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

def web(sid, host, tier=None, name=None, icon=""):
    a = {"name": name or sid, "iconUrl": icon, "searchConfig": {"searchUrl": "https://%s/s?wd={keyword}" % host, "rawBaseUrl": "https://%s" % host}}
    if tier is not None:
        a["tier"] = tier
    return {"id": sid, "factoryId": "web-selector", "version": 2, "arguments": a}

def cand(key, source, status="ok", orig=None):
    c = {"key": key, "origin": "anibaka", "notes": [], "source": source, "smoke": {"status": status}, "chosen": True}
    if orig:
        c["orig_site"] = orig
    return c

# 造一个迷你的官方仓库
repo = tempfile.mkdtemp()
def put(rel, d):
    p = os.path.join(repo, "subs", rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
put("web/t2/路漫漫.json", web("o-lmm", "www.lmm22.com", 2, "路漫漫"))
put("web/t1/2k动漫.json", web("o-2k", "www.mutefun.tv", 1, "2k动漫"))
put("web/t3/Anime7.json", web("o-a7", "anime7.top", 3, "Anime7", icon="https://raw.githubusercontent.com/x/y/main/a7.png"))
put("bt/nyaa.json", {"factoryId": "rss", "arguments": {"name": "nyaa", "searchConfig": {"searchUrl": "https://nyaa.land/?q={keyword}"}}})
open(os.path.join(repo, "subs", "web", "坏文件.json"), "w").write("{not json")
sites = official.load_sites(repo)
check("读到 3 个 web 源，跳过 rss 和坏文件", sorted(s["name"] for s in sites) == ["2k动漫", "Anime7", "路漫漫"])
check("档位读出来了", {s["name"]: s["tier"] for s in sites} == {"路漫漫": 2, "2k动漫": 1, "Anime7": 3})
check("图标域名（github / 百度云 CDN）不参与认站", all(not ({"githubusercontent", "bcebos"} & s["names"]) for s in sites))

# 同名不同后缀 / 站点别名
own = web("aniyuan-lmm", "lmm22.net", 1, icon="https://raw.githubusercontent.com/nlhaiuy/aniyuan/main/icons/aniyuan-lmm.png")
check("后缀不同也是同一个站", [m["name"] for m in official.find_matches(own, sites)] == ["路漫漫"])
mute = web("aniyuan-2kdm", "www.mutedm.com", 1)
check("名字不同、没配别名：认不出", official.find_matches(mute, sites) == [])
check("配了 official_aliases：认得出", [m["name"] for m in official.find_matches(mute, sites, {"mutedm": "mutefun"})] == ["2k动漫"])
moved = web("aniyuan-x", "new-domain.cc", 1)
check("检测时换了域名：原站点也算", [m["name"] for m in official.find_matches(moved, sites, extra=["www.anime7.top"])] == ["Anime7"])
check("两边图标在同一个 CDN：不会误配（真实出现过 次元番 ↔ 嘀哩嘀哩）",
      official.find_matches(web("z", "zzz.com", icon="https://x.cdn.bcebos.com/a.png"), official.load_sites(repo) + [{"name": "别的站", "tier": 4, "source": {}, "names": set(), "path": "p"}]) == [])

def fresh():
    return [cand("lmm", web("aniyuan-lmm", "lmm22.net", 1)), cand("2kdm", web("aniyuan-2kdm", "www.mutedm.com", 1)),
            cand("only", web("aniyuan-only", "only-mine.cc", 1))]
cfg = {"official_aliases": {"mutedm": "mutefun"}}
tiers = lambda cs: {c["key"]: c["source"]["arguments"]["tier"] for c in cs}

# 1. 官方通过：默认降到最低档，独有的不动
cs = fresh()
rows = official.reconcile(cs, sites, cfg, check=lambda s: {"status": "ok"})
check("官方通过：重叠的降到 4，独有的不动", tiers(cs) == {"lmm": 4, "2kdm": 4, "only": 1})
check("报告行：2 行，动作 demote", len(rows) == 2 and all(r["action"] == "demote" for r in rows))
check("降档写进备注", any("降到 4" in n for n in cs[0]["notes"]) and not cs[2]["notes"])

# 2. exclude：官方通过才剔除
cs = fresh()
rows = official.reconcile(cs, sites, dict(cfg, official_dedupe="exclude"), check=lambda s: {"status": "ok"})
check("exclude + 官方通过：剔除", [c.get("dropped") for c in cs] == [True, True, None])
check("剔除的行动作是 drop", {r["action"] for r in rows} == {"drop"})

# 3. 官方失效、自有通过：保留补位，档位不动
cs = fresh()
rows = official.reconcile(cs, sites, dict(cfg, official_dedupe="exclude"), check=lambda s: {"status": "fail"})
check("官方 fail + 自有 ok：保留、不降档、不剔除", tiers(cs) == {"lmm": 1, "2kdm": 1, "only": 1} and not any(c.get("dropped") for c in cs))
check("补位的原因写明", all("补位" in r["note"] for r in rows) and all(r["action"] == "keep" for r in rows))

# 4. 官方没结论 / 没联网：只降档，绝不剔除（哪怕 exclude）
for chk, label in ((lambda s: {"status": "blocked"}, "blocked"), (None, "没联网")):
    cs = fresh()
    official.reconcile(cs, sites, dict(cfg, official_dedupe="exclude"), check=chk)
    check("官方%s + exclude：只降档不剔除" % label, tiers(cs) == {"lmm": 4, "2kdm": 4, "only": 1} and not any(c.get("dropped") for c in cs))

# 5. 官方检测抛异常：当没结论
def boom(s): raise RuntimeError("x")
cs = fresh()
official.reconcile(cs, sites, dict(cfg, official_dedupe="exclude"), check=boom)
check("官方检测抛异常：不影响，只降档", tiers(cs)["lmm"] == 4 and not cs[0].get("dropped"))

# 6. off 什么都不做；非法值报错
cs = fresh()
check("official_dedupe=off：不动", official.reconcile(cs, sites, dict(cfg, official_dedupe="off")) == [] and tiers(cs)["lmm"] == 1)
try:
    official.reconcile(fresh(), sites, {"official_dedupe": "dorp"})
    check("写错的模式要报错", False)
except ValueError:
    check("写错的模式要报错", True)

# 7. 同站有多条官方源：一条通过就算覆盖；本来就在最低档不重复降
put("web/t0/稀饭.json", web("o-x1", "dm1.xfdm.pro", 0, "稀饭动漫"))
put("web/t0/稀饭2.json", web("o-x2", "m.xfdm.pro", 0, "稀饭动漫2"))
sites2 = official.load_sites(repo)
calls = []
def mixed(s):
    calls.append(s["id"]); return {"status": "ok" if s["id"] == "o-x2" else "fail"}
c = cand("xfdm", web("aniyuan-xfdm", "dm1.xfdm.pro", 4))
rows = official.reconcile([c], sites2, {}, check=mixed)
check("多条官方源：一条通过就算覆盖", rows[0]["official_status"] == "ok" and rows[0]["action"] == "keep" and "本来就在最低档" in rows[0]["note"])
check("每个官方源只测一次", sorted(calls) == ["o-x1", "o-x2"])

# 8. 报告
md = "\n".join(official.report_section(official.reconcile(fresh(), sites, cfg, check=lambda s: {"status": "ok"}), 3, "demote"))
check("报告：写出重叠数和独有数", "2 个**和官方订阅重复" in md and "1 个**是官方没有的" in md and "路漫漫（T2）" in md)
check("报告：没有重叠也有一句", "0 个**和官方订阅重复" in "\n".join(official.report_section([], 5, "demote")))

sys.exit(1 if bad else 0)
