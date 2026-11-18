"""Kazumi 规则 searchResult 写成 "."（链接就是列表项本身）时的转换，以及对 smoke 检测的端到端验证（mutefun 的写法）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bs4 import BeautifulSoup
from aniyuan.convert.kazumi import convert_rule

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

RULE = {"api": "9", "type": "anime", "name": "t", "version": "1.0", "baseURL": "https://t.test", "searchURL": "https://t.test/search?q=@keyword",
        "searchList": "//section[contains(@class,'results')]//a[contains(@class,'card')]",
        "searchName": "//span[contains(@class,'title')]", "searchResult": ".",
        "chapterRoads": "//div[contains(@class,'panel')]//div[contains(@class,'list')]", "chapterResult": "//a",
        "searchMode": "xpath", "chapterMode": "xpath", "usePost": False}

r = convert_rule(RULE, {})
check("searchResult 为 \".\" 可以转换", r.source is not None and r.status != "unsupported")
sc = r.source["arguments"]["searchConfig"]
ix = sc["selectorSubjectFormatIndexed"]
check("链接取列表项本身，名称取项内标题", ix["selectLinks"] == 'section[class*="results"] a[class*="card"]'
      and ix["selectNames"] == ix["selectLinks"] + ' span[class*="title"]')

HTML = """<section class="search-results"><a class="video-card" href="/v/1"><span class="video-card-title title">葬送的芙莉莲</span><i>更新中</i></a>
<a class="video-card" href="/v/2"><span class="title">别的番</span></a></section>"""
soup = BeautifulSoup(HTML, "lxml")
links, names = soup.select(ix["selectLinks"]), soup.select(ix["selectNames"])
check("在真实结构上选出条目：链接 / 名称一一对应", [l["href"] for l in links] == ["/v/1", "/v/2"]
      and [n.get_text(strip=True) for n in names] == ["葬送的芙莉莲", "别的番"])

for dot in ("./", " . "):
    rr = convert_rule(dict(RULE, searchResult=dot), {})
    check("写法 %r 同样识别" % dot, rr.source is not None)

# 原有写法不受影响
rr = convert_rule(dict(RULE, searchResult="//a"), {})
check("searchResult 是 //a 时仍走原来的 indexed 写法", rr.source["arguments"]["searchConfig"]["selectorSubjectFormatIndexed"]["selectLinks"].endswith(" a"))
rr = convert_rule(dict(RULE, searchResult=RULE["searchName"]), {})
check("searchName == searchResult 时仍走 a 格式", rr.source["arguments"]["searchConfig"]["subjectFormatId"] == "a")
sys.exit(1 if bad else 0)
