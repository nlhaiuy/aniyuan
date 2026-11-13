"""接口型 Kazumi 规则 -> json-api 数据源：转换映射 + 冒烟检测（只访问本机的模拟接口，不联网）。"""
import json, os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import requests
from aniyuan.convert import kazumi
from aniyuan.check import smoke

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


def rule(**over):
    r = {"api": "9", "name": "demo", "version": "1.0", "baseURL": "https://www.demo.net/", "searchMode": "api",
         "chapterMode": "api", "useWebview": True,
         "searchApiConfig": {"request": {"method": "POST", "url": "https://api.demo.cc/rpc/search", "headers": {"apikey": "k"},
                                         "bodyType": "json", "body": {"term": "@keyword", "page": 1, "items_per_page": 30}},
                             "listPath": "$[*]", "namePath": "$.title", "sourcePath": "$.id"},
         "chapterApiConfig": {"request": {"method": "POST", "url": "https://api.demo.cc/rpc/detail", "headers": {"apikey": "k"},
                                          "bodyType": "json", "body": {"p_id": "@source"}},
                              "format": "nested", "roadsPath": "$.sources[*]", "roadNamePath": "$.name",
                              "episodesPath": "$.episodes[*]", "episodeNamePath": "$.title", "episodeUrlPath": "$.id",
                              "episodePage": {"url": "https://www.demo.net/anime/@source/play/@episodeUrl", "query": {}}}}
    r.update(over)
    return r


# ---------- 转换映射 ----------
res = kazumi.convert_rule(rule(), {})
src = res.source
sc = src["arguments"]["searchConfig"]
check("接口型规则能转成 json-api", res.status == "partial" and src["factoryId"] == "json-api")
check("接口域名和网站域名不同：补 Origin，请求头逐行一条",
      sc["headers"] == "apikey: k\nOrigin: https://www.demo.net")
check("搜索：关键词进请求体，pageSize 取 items_per_page",
      '"term":"{keyword}"' in sc["search"]["request"]["body"] and sc["search"]["pageSize"] == 30)
check("条目页地址从播放页地址截出来", sc["search"]["subjectUrlTemplate"] == "https://www.demo.net/anime/{id}")
check("详情请求体里的 @source 换成 {id}", '"p_id":"{id}"' in sc["subject"]["request"]["body"])
check("有线路名 -> grouped 通道",
      sc["subject"]["channelFormatId"] == "grouped" and sc["subject"]["channelFormatGrouped"]["selectChannelName"] == "$.name")
check("集地址模板：{subjectId} / {id}",
      sc["subject"]["episodes"]["episodeUrlTemplate"] == "https://www.demo.net/anime/{subjectId}/play/{id}")
check("没有序号字段时给出提示", any("序号" in n for n in res.notes))
check("没有 play 时给出提示", any("play" in n for n in res.notes))
check("id / 图标沿用 Kazumi 约定", src["id"] == "kazumi-demo" and src["arguments"]["iconUrl"] == "https://www.demo.net/favicon.ico")

single = rule(chapterApiConfig=dict(rule()["chapterApiConfig"], roadsPath="$.data", roadNamePath="",
                                    episodeNamePath="$.label", episodeUrlPath="$.episodeOrder"))
res = kazumi.convert_rule(single, {})
ep = res.source["arguments"]["searchConfig"]["subject"]
check("单线路：no-channel，剧集路径接在线路路径后面", ep["channelFormatId"] == "no-channel" and ep["episodes"]["selectEpisodes"] == "$.data.episodes[*]")
check("episodeOrder 当作序号", ep["episodes"]["selectSort"] == "$.episodeOrder" and ep["episodes"]["nameTemplate"] == "{sort} {name}")

get_rule = rule(searchApiConfig={"request": {"method": "GET", "url": "https://api.demo.cc/v/list",
                                             "query": {"keyword": "@keyword", "enabled": True, "sortDesc": False}},
                                 "listPath": "$.data.records[*]", "namePath": "$.title", "sourcePath": "$.id"})
u = kazumi.convert_rule(get_rule, {}).source["arguments"]["searchConfig"]["search"]["request"]["url"]
check("GET 查询参数：布尔值写成 true/false", "enabled=true" in u and "sortDesc=false" in u and "keyword={keyword}" in u)

dl = rule(chapterApiConfig=dict(rule()["chapterApiConfig"], format="delimited"))
res = kazumi.convert_rule(dl, {})
check("分隔字符串格式明确报不支持", res.status == "unsupported" and "delimited" in res.notes[0])
check("搜索是网页时明确报不支持", kazumi.convert_rule(rule(searchMode="web", searchApiConfig=None), {}).status == "unsupported")
check("PUT 之类的方法明确报不支持",
      kazumi.convert_rule(rule(searchApiConfig=dict(rule()["searchApiConfig"], request={"method": "PUT", "url": "https://a.b/c"})), {}).status == "unsupported")

# ---------- 冒烟检测（本机模拟接口）----------
STRICT = {"quoted_rejected": False}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, obj):
        raw = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        if self.headers.get("apikey") != "k":
            return self._send(401, {"error": "no key"})
        if self.path == "/rpc/search":
            kw = json.loads(body)["term"]
            if "无结果" in kw:
                return self._send(200, [])
            return self._send(200, [{"id": 7, "title": kw + " 第二季"}, {"id": 8, "title": "别的"}])
        if self.path == "/rpc/detail":
            pid = json.loads(body)["p_id"]
            if STRICT["quoted_rejected"] and isinstance(pid, str):
                return self._send(400, {"error": "p_id must be integer"})
            return self._send(200, {"sources": [{"name": "线路1", "episodes": [{"id": 1, "title": "第1集"}, {"id": 2, "title": "第2集"}]},
                                                {"name": "线路2", "episodes": [{"id": 3, "title": "第1集"}]}]})
        self._send(404, {})


srv = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % srv.server_port
s = requests.Session(); s.trust_env = False
local = json.loads(json.dumps(rule()).replace("https://api.demo.cc", base))
src = kazumi.convert_rule(local, {}).source
r = smoke.check_source(src, "芙莉莲", session=s)
check("json-api 冒烟：搜索 + 详情 + 数出 3 个剧集", r["status"] == "ok" and r["episode_count"] == 3 and "episode_url" not in r)

STRICT["quoted_rejected"] = True
r = smoke.check_source(src, "芙莉莲", session=s)
check("id 带引号被拒（400）：自动改成不带引号并通过", r["status"] == "ok" and r.get("subject_body") == '{"p_id":{id}}')

r = smoke.check_source(src, "无结果", session=s)
check("搜索没有结果：fail（stage=search）", r["status"] == "fail" and r.get("stage") == "search")

bad_key = json.loads(json.dumps(src)); bad_key["arguments"]["searchConfig"]["headers"] = "apikey: wrong"
r = smoke.check_source(bad_key, "芙莉莲", session=s)
check("接口 401：fail，不当成通过", r["status"] == "fail" and "401" in r["reason"])

dead = json.loads(json.dumps(src).replace(base, "http://127.0.0.1:9"))
r = smoke.check_source(dead, "芙莉莲", session=s)
check("接口连不上：unreachable", r["status"] == "unreachable")

srv.shutdown()
print("\n%d 项未通过" % bad if bad else "\n全部通过")
sys.exit(1 if bad else 0)
