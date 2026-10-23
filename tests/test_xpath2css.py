"""用 lxml 的 XPath 结果当标准答案，验证翻译出的 CSS 在 soupsieve 里选中同一批元素。"""
import json, os, random, sys, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lxml import html as LH
from bs4 import BeautifulSoup
from xpath2css import xpath_to_css, Unsupported


def make_doc(seed, depth=5):
    rnd = random.Random(seed)
    counter = [0]
    classes = ["playlist", "row", "anthology-list-play size", "search-list", "module-play-list-content", "box", "x", "hl-plays-list"]
    tags = ["div", "div", "div", "ul", "li", "a", "span", "h3", "h2", "p", "section", "article"]

    def node(d):
        counter[0] += 1
        t = rnd.choice(tags)
        attrs = ' data-i="%d"' % counter[0]
        if rnd.random() < 0.5:
            attrs += ' class="%s"' % rnd.choice(classes)
        if rnd.random() < 0.3:
            attrs += ' id="%s%d"' % (rnd.choice(["playlist", "lists", "box"]), rnd.randint(1, 3))
        if t == "a":
            attrs += ' href="%s"' % rnd.choice(["/play/1", "/vod/play/2", "/x/3"])
        kids = ""
        if d < depth and t not in ("a", "span", "h2", "h3", "p"):
            kids = "".join(node(d + 1) for _ in range(rnd.randint(1, 4)))
        else:
            kids = "t%d" % counter[0]
        return "<%s%s>%s</%s>" % (t, attrs, kids, t)

    return "<html><body>%s</body></html>" % "".join(node(1) for _ in range(rnd.randint(2, 4)))


def xpath_ids(doc, xp):
    tree = LH.fromstring(doc)
    return sorted(int(e.get("data-i")) for e in tree.xpath(xp) if e.get("data-i"))


def css_ids(doc, css):
    soup = BeautifulSoup(doc, "lxml")
    return sorted(int(e["data-i"]) for e in soup.select(css) if e.has_attr("data-i"))


FIXTURES = [
    """<html><body><div data-i="1" class="playlist"><div data-i="2" class="row"><ul data-i="3"><li data-i="4"><a data-i="5" href="/play/1">1</a></li><li data-i="6"><a data-i="7" href="/play/2">2</a></li></ul><ul data-i="8"><li data-i="9"><a data-i="10" href="/play/3">3</a></li></ul></div></div>
    <div data-i="11" class="search-box"><ul data-i="12"><li data-i="13"><h3 data-i="14"><a data-i="15" href="/x/1">t</a></h3><h2 data-i="16"><a data-i="17" href="/x/1">t</a></h2></li><li data-i="18"><h3 data-i="19"><a data-i="20" href="/x/2">u</a></h3></li></ul></div></body></html>""",
    """<html><body><div data-i="1"><div data-i="2"></div><div data-i="3"><div data-i="4"><div data-i="5"></div><div data-i="6"><div data-i="7"><div data-i="8"></div><div data-i="9"><a data-i="10" href="/p">x</a><div data-i="11"><div data-i="12"></div></div></div></div></div></div></div></div>
    <div data-i="13"><div data-i="14"><div data-i="15"><div data-i="16"><div data-i="17"></div><div data-i="18"><div data-i="19"><a data-i="20" href="/q">y</a></div></div></div></div></div></div></body></html>""",
    """<html><body><div data-i="1"></div><div data-i="2"><div data-i="3"></div><div data-i="4"><div data-i="5"><div data-i="6"></div><div data-i="7"><div data-i="8"><div data-i="9"><div data-i="10"></div><div data-i="11"></div></div><div data-i="12"><div data-i="13"></div></div></div></div></div></div></body></html>""",
    """<html><body><div data-i="1" class="hl-play-source x"><div data-i="2"><ul data-i="3" class="a hl-plays-list b"><li data-i="4"><a data-i="5" href="/vod/play/9">1</a></li></ul></div></div><div data-i="6" id="playlist1" class="lists-box"><a data-i="7" href="/index.php/vod/play/1">1</a></div></body></html>""",
]


CASES = [
    "//div", "//div/div", "//div[2]", "//div[2]/div[1]/div[2]", "//div/div/div[2]/div/a",
    "//ul/li/a", "//li/a", "//a", "//div[@class='playlist']/div[@class='row']/ul",
    "//ul[@class='anthology-list-play size']", "//div[contains(@class, 'search')]/ul/li",
    "//div[starts-with(@id, 'playlist')][contains(@class, 'box')]",
    "//div[contains(@class,'hl-play-source')]//ul[contains(@class,'hl-plays-list')]",
    "//div[2]/div[2]/div[2]/div/div[2]/div[1]//div", "//section/div[1]/ul[1]/li",
    "//a[contains(@href, '/play/')]", "//div//a[@href]", "//h3/a", "//h2/a",
]


def main():
    bad = 0
    total = 0
    for xp in CASES:
        css, _ = xpath_to_css(xp)
        diffs = 0
        nonempty = 0
        for seed in range(150 + len(FIXTURES)):
            doc = make_doc(seed) if seed < 150 else FIXTURES[seed - 150]
            a, b = xpath_ids(doc, xp), css_ids(doc, css)
            total += 1
            if a:
                nonempty += 1
            if a != b:
                diffs += 1
        status = "OK " if diffs == 0 else "BAD"
        print(status, xp, "->", css, "(非空文档 %d/%d)" % (nonempty, 150 + len(FIXTURES)))
        bad += diffs
    # 相对路径(.//a) 与 item 组合: 在 item 内用 CSS 后代，等价于 XPath 的 .//
    # 真实规则也跑一遍，确认至少都能翻译或明确报告不支持
    rules_dir = os.environ.get("KAZUMI_RULES")
    if rules_dir:
        ok = uns = 0
        for f in sorted(glob.glob(os.path.join(rules_dir, "*.json"))):
            r = json.load(open(f))
            if not isinstance(r, dict):
                continue
            for k in ("searchList", "searchName", "searchResult", "chapterRoads", "chapterResult"):
                if r.get(k):
                    try:
                        xpath_to_css(r[k]); ok += 1
                    except Unsupported:
                        uns += 1
        print("真实规则字段：可翻译 %d，不支持 %d" % (ok, uns))
    print("不一致文档数：%d / %d" % (bad, total))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
