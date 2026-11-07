"""选择器自动修复的自测（不联网）：候选库和排序规则。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan.check.repair import find_search_selector, find_episode_selector, mine_presets, repair_source

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

# 7. matchVideoUrl 修复
from aniyuan.check.repair import propose_match_video, repair_match_video
from aniyuan.convert.kazumi import MATCH_VIDEO_URL as DEFAULT_MV
from aniyuan.check.playcheck import to_py_regex
import re as _re
def mv_ok(pat, url): return bool(_re.search(to_py_regex(pat), url))
pat, why = propose_match_video(r"never\.flv", ["https://v.cdn1.example.com/a/index.m3u8?x=1"], DEFAULT_MV)
check("matchVideoUrl：通用写法认得出就用通用写法", pat == DEFAULT_MV and mv_ok(pat, "https://v.cdn1.example.com/a/index.m3u8?x=1"))
pat, why = propose_match_video("", ["https://x.example.com/p/vid?id=1"], DEFAULT_MV)
check("matchVideoUrl：既没有后缀又不是已知形态 -> 不乱改", pat is None)
pat, why = propose_match_video("", ["https://x.example.com/a/b.ts"], DEFAULT_MV)
check("matchVideoUrl：只有 .ts 分片 -> 不采用", pat is None)
pat, why = propose_match_video("", [], DEFAULT_MV)
check("matchVideoUrl：没有观察到的地址 -> 不改", pat is None)
# 地址里还嵌着别的 http://（嵌套地址）属于 matchNestedUrl 的事，不在这里乱猜
pat, why = propose_match_video(r"never\.flv", ["https://p.example.org/x?redirect=http://q.example.org/a.mpd"], DEFAULT_MV)
check("matchVideoUrl：嵌套地址不乱猜", pat is None)
# 写得太宽的会被拒绝：模拟旧写法 .* 并上通用写法其实不会变窄，所以检查“限定写法不认 ts/图片/脚本”
pat, why = propose_match_video("", ["https://cdn.example.com/hls/index.mpd"], DEFAULT_MV)
check("matchVideoUrl：.mpd 这类通用写法没有的后缀，用限定主域名的写法", bool(pat) and mv_ok(pat, "https://cdn.example.com/hls/index.mpd")
      and not mv_ok(pat, "https://cdn.example.com/hls/seg001.ts") and not mv_ok(pat, "https://cdn.example.com/cover.jpg"))
pat, why = propose_match_video("", ["http://127.0.0.1:8080/m/9.mpd"], DEFAULT_MV)
check("matchVideoUrl：带端口的 IP 主机也能写出限定写法", bool(pat) and mv_ok(pat, "http://127.0.0.1:8080/m/9.mpd") and not mv_ok(pat, "http://127.0.0.1:8080/m/a.ts"))
src = {"arguments": {"description": "d", "searchConfig": {"matchVideo": {"matchVideoUrl": r"never\.flv", "cookies": "q=1"}}}}
new, why = repair_match_video(src, ["https://v.example.com/a.m3u8"], DEFAULT_MV)
check("repair_match_video：只改 matchVideoUrl，其余字段保留，描述带标记，不改原对象",
      new and new["arguments"]["searchConfig"]["matchVideo"]["matchVideoUrl"] == DEFAULT_MV
      and new["arguments"]["searchConfig"]["matchVideo"]["cookies"] == "q=1" and new["arguments"]["description"].startswith("[匹配规则已自动修复]")
      and src["arguments"]["searchConfig"]["matchVideo"]["matchVideoUrl"] == r"never\.flv")
check("repair_match_video：没有 matchVideo 的源不动", repair_match_video({"arguments": {"searchConfig": {}}}, ["https://v/a.m3u8"], DEFAULT_MV)[0] is None)
sys.exit(1 if bad else 0)
