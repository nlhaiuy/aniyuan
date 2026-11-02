"""选择器自动修复的自测（不联网）：候选库和排序规则。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repair import find_search_selector, find_episode_selector, mine_presets, repair_source

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


presets = mine_presets(None)
NAV = '<ul class="nav"><li><a href="/type/1.html">动漫</a></li><li><a href="/type/2.html">电影</a></li></ul>'

# 1. 详情页路径不在候选里（/zzz/）：靠不限路径的兜底 + 标题容器选出来，而且不会把导航链接选进来
html = NAV + '<div class="box"><h4 class="title"><a href="/zzz/9.html">葬送的芙莉莲</a></h4></div>'
r = find_search_selector(html, "葬送的芙莉莲", presets)
check("未知详情页路径：用兜底选出结果链接", bool(r) and r[1] == 1 and r[2] == 1 and r[3][1] == "/zzz/9.html")

# 2. 已知路径：同样精确时仍选限定了链接路径的（更不容易被改版误伤）
html = NAV + '<div class="module-card-item-title"><a href="/detail/1.html">葬送的芙莉莲</a></div>'
r = find_search_selector(html, "葬送的芙莉莲", presets)
check("已知路径：同分时优先带路径的选择器", bool(r) and "/detail/" in r[0] and r[1] == r[2] == 1)

# 3. 兜底不能压过更精确的：结果里混着一个同名的推荐链接，带路径的命中率更高
html = ('<div class="hot"><a href="/zzz/5.html">葬送的芙莉莲 外传</a><a href="/zzz/6.html">别的</a><a href="/zzz/7.html">别的2</a></div>'
        '<div class="list"><a href="/detail/1.html">葬送的芙莉莲</a></div>')
r = find_search_selector(html, "葬送的芙莉莲", presets)
check("命中率优先：选命中率最高的", bool(r) and r[1] == 1 and r[2] == 1)

# 4. 搜索页没有结果：返回 None
check("搜索页没有结果返回 None", find_search_selector(NAV, "葬送的芙莉莲", presets) is None)

# 5. 参考订阅里常见的剧集列表容器
for cls in ("jisu", "movurl", "videolist", "fed-play-item", "anime-episode"):
    html = '<div class="%s"><a href="/p/1">第1集</a><a href="/p/2">第2集</a><a href="/p/3">第3集</a></div>' % cls
    ep = find_episode_selector(html, presets)
    check("剧集列表 .%s" % cls, bool(ep) and ep[1] == 3 and cls in ep[0])

# 6. 端到端：搜索选择器 + 剧集选择器一起修
detail = '<div class="jisu"><a href="/p/1">第1集</a><a href="/p/2">第2集</a></div>'
src = {"arguments": {"searchConfig": {"subjectFormatId": "indexed"}}}
ctx = {"search_url": "https://e.com/s?wd=x", "search_html": NAV + '<div class="box"><h4><a href="/zzz/9.html">葬送的芙莉莲</a></h4></div>'}
fetched = []
new, note = repair_source(src, ctx, "葬送的芙莉莲", presets, lambda u: (fetched.append(u) or detail), "both")
sc = (new or {}).get("arguments", {}).get("searchConfig", {})
check("端到端修复：搜索和剧集选择器都改了", bool(new) and sc.get("subjectFormatId") == "a"
      and sc.get("selectorChannelFormatNoChannel", {}).get("selectEpisodes") == ".jisu a" and fetched == ["https://e.com/zzz/9.html"])
check("端到端修复：不改原对象", src["arguments"]["searchConfig"] == {"subjectFormatId": "indexed"})
sys.exit(1 if bad else 0)
