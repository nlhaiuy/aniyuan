"""从播放页「学」出 json-api 数据源的 play（取视频地址的请求）。

Animeko 的 json-api 数据源必须有 play。Kazumi 的接口规则里没有播放接口（网页前端的 JS 写死调用的），
官方订阅里找不到同一接口的源时，就用无头浏览器自己把它学出来：

  1. 打开两三集的播放页，记下页面发出的 XHR / fetch 请求和响应；
  2. 找响应 JSON 里带视频地址（m3u8 / mp4……）的那个请求，推出 selectCandidates / selectVideoUrl（JSONPath）；
  3. 对比「第 A 集」和「第 B 集」两次请求：值恰好等于各自剧集 id 的地方换成 {id}，两次都不变的保持原样。
     只看一次的话 page=1 和 id=1 分不出来，两集对比才可靠；
  4. 请求头只留两次一致、不是浏览器常规头的（比如 apikey）；会变的（临时 token / 签名）不留；
  5. 用 requests 拿第三集（没有就用第二集）把学到的 play 重放一遍，能取出视频地址才采用。
     重放失败时补上浏览器当时发的 Referer / Origin 再试一次。

学到的 play 按接口指纹缓存（state/play.json）：接口没变就直接沿用，只用 requests 重放验证，不再开浏览器。
学不出来（需要登录、签名、请求头里有一次性 token、视频地址不在 JSON 里……）就返回原因，由调用方决定怎么办。
"""
import copy
import hashlib
import json
import re

from . import smoke as smoke_mod
from .playcheck import MEDIA_RE

# 浏览器自己会带的请求头：不属于接口要求，不抄
SKIP_HEADERS = {"host", "connection", "content-length", "user-agent", "accept", "accept-language", "accept-encoding",
                "origin", "referer", "cookie", "priority", "upgrade-insecure-requests", "content-type", "pragma",
                "cache-control", "dnt", "te"}
CHANNEL_KEYS = ["source_name", "channel", "channel_name", "source", "line", "line_name", "route", "name", "title"]
INT_MARK, STR_MARK = "__AY_ID_INT__", "__AY_ID_STR__"
_KEY = re.compile(r"^\w+$")


# ------------------------------- 找视频地址 -------------------------------

def is_media(v):
    return isinstance(v, str) and v.startswith(("http://", "https://")) and bool(MEDIA_RE.search(v))


def loads(text):
    text = (text or "").strip()
    if not text or text[0] not in "{[":
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def find_media_paths(obj, path=(), depth=0):
    """JSON 里所有视频地址的位置：[(路径, 地址)]；路径里的列表层用 "[*]" 表示。"""
    out = []
    if depth > 8:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += find_media_paths(v, path + (str(k),), depth + 1)
    elif isinstance(obj, list):
        for v in obj[:50]:
            out += find_media_paths(v, path + ("[*]",), depth + 1)
    elif is_media(obj):
        out.append((path, obj))
    return out


def selectors_for(tokens, channels=()):
    """路径 -> (selectCandidates, selectVideoUrl)；只支持一层列表、键名是字母数字下划线。不支持返回 None。"""
    tokens = list(tokens)
    if any(t != "[*]" and not _KEY.match(t) for t in tokens):
        return None
    n = tokens.count("[*]")
    if n == 0:
        return "", "$." + ".".join(tokens)
    if n > 1:
        return None
    i = tokens.index("[*]")
    rel = tokens[i + 1:]
    if not rel:
        return None
    head = "$" + "".join("." + t for t in tokens[:i])
    return head + "[*]", "$." + ".".join(rel)


def pick_channel_field(candidate, channels):
    """候选里哪个字段是线路名：值等于详情接口里某条线路名的优先；否则按常见字段名猜。"""
    if not isinstance(candidate, dict):
        return ""
    for k, v in candidate.items():
        if _KEY.match(str(k)) and isinstance(v, str) and v in set(channels):
            return "$." + k
    for k in CHANNEL_KEYS:
        if isinstance(candidate.get(k), str) and candidate[k]:
            return "$." + k
    return ""


# ------------------------------- 把 id 换成 {id} -------------------------------

def _id_re(i):
    return re.compile(r"(?<![0-9A-Za-z])%s(?![0-9A-Za-z])" % re.escape(str(i)))


def template_text(a, id_a, b, id_b):
    """地址 / 表单：把各自的剧集 id 换成 {id}，两边一致才算模板；返回 None 表示对不上。"""
    ta, tb = _id_re(id_a).sub("{id}", a or ""), _id_re(id_b).sub("{id}", b or "")
    if str(id_a) == str(id_b):
        return ta
    return ta if ta == tb else None


def _merge(a, b, id_a, id_b, same_id, unstable):
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: _merge(a[k], b[k], id_a, id_b, same_id, unstable) if k in b else a[k] for k in a}
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [_merge(x, y, id_a, id_b, same_id, unstable) for x, y in zip(a, b)]
    if str(a) == str(id_a) and (same_id or str(b) == str(id_b)) and not isinstance(a, (bool, float)) and a is not None:
        return INT_MARK if isinstance(a, int) else STR_MARK
    if a != b and not same_id:
        unstable.append(a)   # 两次请求这个值不一样、又不是剧集 id：时间戳 / 随机数 / 签名
    return a


def template_json(a_text, id_a, b_text, id_b):
    """JSON 请求体：值恰好等于各自剧集 id 的地方换成 {id}（数字不带引号、字符串带引号），
    两次都不变的保持原样。返回 (模板文本, 会变的值列表)；不是 JSON 返回 (None, [])。"""
    ja, jb = loads(a_text), loads(b_text)
    if ja is None or jb is None:
        return None, []
    unstable = []
    merged = _merge(ja, jb, id_a, id_b, str(id_a) == str(id_b), unstable)
    text = json.dumps(merged, ensure_ascii=False, separators=(",", ":"))
    return text.replace('"%s"' % INT_MARK, "{id}").replace('"%s"' % STR_MARK, '"{id}"'), unstable


def learned_headers(ha, hb, common):
    """两次请求一致、不是浏览器常规头、也不是公共请求头里已经有的，才抄。"""
    have = smoke_mod._header_dict(common)
    out = []
    for k, v in (ha or {}).items():
        lk = k.lower()
        if lk in SKIP_HEADERS or lk.startswith(("sec-", ":")):
            continue
        if hb is not None and (hb.get(k) != v):
            continue
        if have.get(k) == v or any(x.lower() == lk and y == v for x, y in have.items()):
            continue
        out.append("%s: %s" % (k, v))
    return "\n".join(out)


# ------------------------------- 学习与验证 -------------------------------

def extract(sc, data, play):
    """按 play 的选择路径从响应里取视频地址 [(线路名, 地址)]。"""
    ev = smoke_mod.eval_simple_jsonpath
    cands = ev(data, play["selectCandidates"]) if play.get("selectCandidates") else [data]
    out = []
    for c in cands:
        urls = ev(c, play["selectVideoUrl"])
        ch = ev(c, play["selectCandidateChannel"]) if play.get("selectCandidateChannel") else []
        if urls and isinstance(urls[0], str) and urls[0]:
            out.append((str(ch[0]) if ch else "", urls[0]))
    return out


def verify(session, sc, play, ep_id, timeout=15):
    """用 requests 重放 play 请求：能取出视频地址才算通过。返回 (是否通过, 原因, 视频地址)。"""
    try:
        r = smoke_mod._api_call(session, sc, play["request"], {"id": ep_id}, timeout)
    except Exception as e:
        return False, "重放请求失败：%s" % type(e).__name__, ""
    data, bad = smoke_mod._api_json(r)
    if bad:
        return False, "重放 play：" + bad[1], ""
    try:
        got = extract(sc, data, play)
    except ValueError as e:
        return False, str(e), ""
    good = [u for _, u in got if is_media(u) or u.startswith(("http://", "https://"))]
    if not good:
        return False, "重放 play 能打开，但选择路径没有取出视频地址", ""
    return True, "", good[0]


def _entry_template(entry_a, entry_b, id_a, id_b):
    """把一对请求（同一个接口在两集上的请求）推成 play 的 request；对不上返回 (None, 原因)。"""
    if entry_a["method"] != entry_b["method"]:
        return None, "两集的请求方法不一样"
    url = template_text(entry_a["url"], id_a, entry_b["url"], id_b)
    if url is None:
        return None, "两集的请求地址对不上"
    body, unstable = "", []
    if entry_a.get("post"):
        body, unstable = template_json(entry_a["post"], id_a, entry_b.get("post") or "", id_b)
        if body is None:
            body = template_text(entry_a["post"], id_a, entry_b.get("post") or "", id_b)
            if body is None:
                return None, "两集的请求体对不上"
    if unstable:
        return None, "请求体里有每次都会变的值（时间戳 / 随机数 / 签名）：%s" % str(unstable[0])[:30]
    return {"url": url, "method": entry_a["method"], "body": body or "", "headers": ""}, ""


def _stop_when_media(entries):
    return any(find_media_paths(loads(e["text"])) for e in entries if loads(e["text"]) is not None)


def learn(pc, sc, sample, session, wait_ms=20000, ua=None):
    """返回 (play 或 None, 说明)。sample 是 smoke 给的：{"subject_id", "channels", "episodes": [{id, name, channel, url}]}。"""
    eps = (sample or {}).get("episodes") or []
    if not eps or not eps[0].get("url"):
        return None, "没有可用的剧集样本（详情接口没有选出带播放页地址的剧集）"
    A = eps[0]
    B = eps[1] if len(eps) > 1 else None
    C = eps[2] if len(eps) > 2 else (B or A)
    cap_a = pc.capture(A["url"], wait_ms, ua, stop=_stop_when_media)
    hits = []
    for e in cap_a:
        data = loads(e["text"])
        if data is None:
            continue
        paths = find_media_paths(data)
        if paths:
            hits.append((e, data, paths[0]))
    if not hits:
        n = len(cap_a)
        return None, "播放页没有发出带视频地址的 JSON 接口请求（共抓到 %d 个 XHR/fetch；视频地址可能在页面 HTML / iframe 里，或需要登录 / 点击）" % n
    cap_b = pc.capture(B["url"], wait_ms, ua) if B else []
    why = "没有候选"
    for ea, data, (tokens, _url) in hits:
        sel = selectors_for(tokens)
        if sel is None:
            why = "视频地址的位置（%s）无法写成 JSONPath" % "/".join(tokens)
            continue
        eb = ea
        if B:
            eb = next((x for x in cap_b if x["method"] == ea["method"]
                       and template_text(ea["url"], A["id"], x["url"], B["id"]) is not None and find_media_paths(loads(x["text"]))), None)
            if eb is None:
                why = "第二集的播放页没有发出同一个接口的请求"
                continue
        req, bad = _entry_template(ea, eb, A["id"], B["id"] if B else A["id"])
        if req is None:
            why = bad
            continue
        play = {"request": req, "selectCandidates": sel[0], "selectCandidateChannel": "", "selectVideoUrl": sel[1],
                "fallbackToFirstCandidate": True, "referer": ""}
        cand_elems = smoke_mod.eval_simple_jsonpath(data, sel[0]) if sel[0] else []
        ch = pick_channel_field(cand_elems[0] if cand_elems else None, (sample or {}).get("channels") or [])
        if ch:
            play["selectCandidateChannel"], play["fallbackToFirstCandidate"] = ch, False
        play["request"]["headers"] = learned_headers(ea["headers"], eb["headers"] if B else None, sc.get("headers", ""))
        ok, bad, media = verify(session, sc, play, C["id"])
        if not ok:   # 补上浏览器当时发的 Referer / Origin 再试一次
            extra = "\n".join("%s: %s" % (k, ea["headers"][k]) for k in ("referer", "origin") if ea["headers"].get(k))
            if extra:
                retry = copy.deepcopy(play)
                retry["request"]["headers"] = (play["request"]["headers"] + "\n" + extra).strip()
                ok, bad2, media = verify(session, sc, retry, C["id"])
                if ok:
                    play = retry
        if ok:
            weak = "" if B else "；只有一集，id 的位置只能按值相等推断，较弱"
            return play, "从「%s」的播放页学到，已用「%s」重放验证（视频地址 %s）%s" % (
                A["name"] or A["id"], C["name"] or C["id"], media[:80], weak)
        why = bad
    return None, "学到了候选接口但重放验证没通过：%s" % why


# ------------------------------- 缓存与流程 -------------------------------

def fingerprint(sc):
    """接口指纹：这些变了，学到的 play 就不一定还能用，要重新学。"""
    sub = sc.get("subject") or {}
    key = [sc.get("baseUrl"), (sub.get("request") or {}).get("url"), (sub.get("request") or {}).get("method"),
           (sub.get("episodes") or {}).get("selectId"), (sub.get("episodes") or {}).get("episodeUrlTemplate")]
    return hashlib.sha1(json.dumps(key, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def learn_plays(cands, pc, session, cache, now, wait_ms=20000):
    """给 needs_play 的候选补 play：先用缓存（能重放验证就验证），不行再用浏览器学。cache 就地更新。"""
    for c in cands:
        src = c.get("source")
        if not c.get("needs_play") or not src or src.get("factoryId") != "json-api":
            continue
        sc = src["arguments"]["searchConfig"]
        fp = fingerprint(sc)
        sample = (c.get("smoke") or {}).get("sample") or {}
        eps = sample.get("episodes") or []
        cached = cache.get(src["id"])
        play, note = None, ""
        if cached and cached.get("fp") == fp:
            if eps:
                ok, bad, _ = verify(session, sc, cached["play"], eps[-1]["id"])
                if ok:
                    play, note = cached["play"], "沿用上次从播放页学到的 play（已重放验证）"
                else:
                    c["notes"].append("上次学到的 play 重放没通过（%s），重新学" % bad)
            elif (c.get("smoke") or {}).get("status") != "ok":
                play, note = cached["play"], "本次没检测到条目，沿用上次学到的 play（未验证）"
        if play is None and pc is not None and eps:
            try:
                play, note = learn(pc, sc, sample, session, wait_ms, (sc.get("userAgent") or "").strip() or None)
            except Exception as e:
                play, note = None, "学习 play 时出错：%s" % type(e).__name__
        if play:
            sc["play"] = play
            c["needs_play"] = False
            c["status"] = "partial"
            c["notes"] = [n for n in c["notes"] if "没有播放接口" not in n] + ["播放接口（play）：" + note]
            cache[src["id"]] = {"fp": fp, "play": play, "learned": now}
        elif note:
            c["notes"].append("从播放页学习 play 失败：" + note)
        elif not eps:
            c["notes"].append("没有检测到可用的剧集，没法从播放页学习 play")
    return cache


def check_plays(cands, session):
    """json-api 源的播放检测：用 requests 重放 play 请求（不开浏览器），取得到视频地址就是 ok，取不到是 none。
    不管 play 是借官方的、学来的还是缓存的都检，官方写法过期 / 接口变了能在报告里看出来，也参与自动排序。"""
    for c in cands:
        src = c.get("source")
        if not src or src.get("factoryId") != "json-api" or (c.get("smoke") or {}).get("status") != "ok":
            continue
        sc = src["arguments"]["searchConfig"]
        eps = ((c["smoke"].get("sample") or {}).get("episodes")) or []
        if not sc.get("play") or not eps:
            continue
        ok, bad, media = verify(session, sc, sc["play"], eps[-1]["id"])
        c["smoke"]["play"] = "ok" if ok else "none"
        c["smoke"]["play_reason"] = ("重放 play 取到视频地址：" + media[:120]) if ok else bad
