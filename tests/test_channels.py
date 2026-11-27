"""自动分线路（check/channels.py）和逐线路播放检测的自测（不联网）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan.check import channels
from aniyuan.check.smoke import extract_episodes
from aniyuan.build import regroup, keep_lines, check_lines

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


BASE = "https://x.com/detail/1.html"


def box(line, n, cls="anthology-list-box"):
    return '<div class="%s"><ul>%s</ul></div>' % (cls, "".join(
        '<li><a href="/play/1-%d-%d.html">第%02d集</a></li>' % (line, i, i) for i in range(1, n + 1)))


def page(tabs, boxes, extra="", tabcls="anthology-tab"):
    return '<html><body><ul class="nav-tabs"><li>首页</li><li>电影</li></ul><div class="%s">%s</div>%s%s</body></html>' % (
        tabcls, "".join("<a>%s</a>" % t for t in tabs), "".join(boxes), extra)


def source(sel=".anthology-list-box a"):
    return {"id": "aniyuan-x", "factoryId": "web-selector", "version": 2, "arguments": {"name": "x", "tier": 4, "searchConfig": {
        "searchUrl": "https://x.com/s?wd={keyword}", "channelFormatId": "no-channel",
        "selectorChannelFormatNoChannel": {"selectEpisodes": sel, "matchEpisodeSortFromName": r"(第\s*(?<ep>.+?)\s*[话集])|(\d+)"},
        "selectMedia": {"distinguishSubjectName": True, "distinguishChannelName": False}}}}


two = page(["线路一<span>3</span>", "线路二<span>2</span>"], [box(1, 3), box(2, 2)])
src = source()
new, fl = channels.upgrade(src, two, BASE)
sc = new["arguments"]["searchConfig"]
check("两条线路：升级成 index-grouped 并区分线路名",
      sc["channelFormatId"] == "index-grouped" and sc["selectMedia"]["distinguishChannelName"] is True)
check("集数角标从线路名里去掉", [n for n, _ in channels.lines_of(sc, two, BASE)] == ["线路一", "线路二"])
check("分组后剧集和合并写法完全一致", len(extract_episodes(sc, two, BASE)) == 5)
check("原来的源对象没被改动", src["arguments"]["searchConfig"]["channelFormatId"] == "no-channel")

nums = page(["线路1", "线路2"], [box(1, 5), box(2, 5)])
new, _ = channels.upgrade(source(), nums, BASE)
check("“线路1 / 线路2”保留数字，不会并成同名",
      [n for n, _ in channels.lines_of(new["arguments"]["searchConfig"], nums, BASE)] == ["线路1", "线路2"])

check("只有一条线路：不升级", channels.upgrade(source(), page(["线路一"], [box(1, 3)]), BASE)[0] is None)
check("标签数量对不上：不升级", channels.upgrade(source(), page(["A", "B", "C"], [box(1, 3), box(2, 3)]), BASE)[0] is None)
check("网站导航不会被当成线路（首页 / 电影 正好 2 个）",
      channels.upgrade(source(), page([], [box(1, 3), box(2, 3)]), BASE)[0] is None)
check("分页标签（1-50）不是线路",
      channels.upgrade(source(), page(["1-50", "51-100"], [box(1, 3), box(2, 3)]), BASE)[0] is None)
check("两个列表内容重复（手机 / 电脑各一份）：不升级",
      channels.upgrade(source(), page(["A线", "B线"], [box(1, 3), box(1, 3)]), BASE)[0] is None)
partial = page(["A线", "B线"], [box(1, 3), box(2, 3)], extra=box(3, 3, "other"))
check("列表容器盖不全合并写法的剧集：不能丢集",
      channels.upgrade(source(".anthology-list-box a, .other a"), partial, BASE)[0] is None)

derived = page(["A线", "B线"], [box(1, 3, "weird-eps"), box(2, 3, "weird-eps")])
check("不在常见清单里的模板：从祖先 class 推出列表容器",
      channels.upgrade(source(".weird-eps a"), derived, BASE)[0] is not None)

custom = page(["A线", "B线"], [box(1, 3), box(2, 3)], tabcls="zz-tabs")
sites = [{"source": {"arguments": {"searchConfig": {"channelFormatId": "index-grouped", "selectorChannelFormatFlattened": {
    "selectChannelNames": ".zz-tabs a", "selectEpisodeLists": ".anthology-list-box"}}}}}]
check("不认识的标签写法：没有官方写法时不升级", channels.upgrade(source(), custom, BASE)[0] is None)
check("借官方订阅里的写法后能升级",
      channels.upgrade(source(), custom, BASE, presets=channels.official_presets(sites))[0] is not None)

icons = page(["\ue679&nbsp;高画线", "\ue679&nbsp;中画线"], [box(1, 3), box(2, 3)])
new, _ = channels.upgrade(source(), icons, BASE)
check("标签前的图标字体字符不进线路名",
      [n for n, _ in channels.lines_of(new["arguments"]["searchConfig"], icons, BASE)] == ["高画线", "中画线"])

# 响应头没写 charset：不能按 ISO-8859-1 解出乱码
import requests
from aniyuan.check.smoke import fix_encoding
def resp(body, ctype):
    r = requests.Response()
    r._content, r.headers["content-type"], r.encoding = body, ctype, "ISO-8859-1"
    return r
check("没写 charset 的 UTF-8 页面按 UTF-8 解", fix_encoding(resp("聚合线路".encode("utf-8"), "text/html")).text == "聚合线路")
check("写了 charset 的照它的来", fix_encoding(resp(b"abc", "text/html; charset=ISO-8859-1")).encoding == "ISO-8859-1")

# Animeko 的配对语义
fl = {"selectChannelNames": ".anthology-tab a", "matchChannelName": channels.FULL_NAME, "selectEpisodeLists": ".anthology-list-box",
      "selectEpisodesFromList": "a"}
hole = page(["A线", ""], [box(1, 2), box(2, 2)])
check("标签为空：对应列表在 Animeko 里看不到", [n for n, _ in channels.simulate(fl, hole, BASE)] == ["A线"])
grouped_sc = {"channelFormatId": "index-grouped", "selectorChannelFormatFlattened": dict(fl, selectChannelNames=".nothing")}
check("线路标签选不中：检测按 0 集算（以前会误报通过）", extract_episodes(grouped_sc, two, BASE) == [])
check("没写 matchChannelName 时按 Animeko 默认值去掉末尾数字",
      [n for n, _ in channels.simulate({k: v for k, v in fl.items() if k != "matchChannelName"}, nums, BASE)] == ["线路", "线路"])

# 缓存与 build 接线
def cand(status="ok"):
    return dict(origin="kazumi", key="x", source=source(), notes=[], smoke={"status": status, "episode_url": None})

cache = {}
c = cand()
regroup(c, {"detail_html": two, "detail_url": BASE}, cache, ((), ()), {})
check("regroup：写缓存、记下每条线路第一集", "kazumi:x" in cache and len(c["lines"]) == 2)
c2 = cand("unreachable")
keep_lines([c2], cache, {})
check("这次打不开：沿用缓存的分线路写法", c2["source"]["arguments"]["searchConfig"]["channelFormatId"] == "index-grouped")
c3 = cand("unreachable")
c3["source"] = source(".changed a")
keep_lines([c3], cache, {})
check("上游规则变了：缓存作废", c3["source"]["arguments"]["searchConfig"]["channelFormatId"] == "no-channel")
c4 = cand()
regroup(c4, {"detail_html": two, "detail_url": BASE}, {}, ((), ()), {"auto_channels": False})
check("auto_channels=false：关闭", c4["source"]["arguments"]["searchConfig"]["channelFormatId"] == "no-channel")


class FakePC:
    def __init__(self, ok):
        self.ok, self.calls = ok, []
    def check(self, source, url, wait, extra):
        self.calls.append(url)
        return {"play": "ok" if url in self.ok else "none"}


lines = [("A", "u1"), ("B", "u2"), ("C", "u3")]
c = dict(notes=[], lines=lines, source=source(), smoke={"status": "ok", "play": "none", "episode_url": "u1"})
pc = FakePC({"u2"})
check_lines([c], {}, pc)
check("默认线路播不了、别的能播：整个源按能播算", c["smoke"]["play"] == "ok" and pc.calls == ["u2", "u3"])
check("逐线路结果", c["line_play"] == {"A": "none", "B": "ok", "C": "none"})
check("channelTiers 只把没验证能播的线路排后面", channels.channel_tiers(c["line_play"], 1) == {"A": 5, "C": 5})
check("官方重叠降到 4 档时，不能播的仍排在后面且不抬高能播的", channels.channel_tiers(c["line_play"], 4) == {"A": 5, "C": 5})
check("全部没验证出能播：不写（避免偶发结果压档）", channels.channel_tiers({"A": "none", "B": "none"}, 2) == {})
pc = FakePC(set())
c = dict(notes=[], lines=lines, source=source(), smoke={"status": "ok", "play": "ok", "episode_url": "u1"})
check_lines([c], {"line_check_max": 1}, pc)
check("总次数上限生效", pc.calls == ["u2"] and "C" not in c["line_play"])

print("\n全部通过" if not bad else "\n%d 项失败" % bad)
sys.exit(1 if bad else 0)
