"""可选的出口代理：检测跑在 GitHub 的海外服务器上，很多国内站从海外访问不了（unreachable）或被拦（blocked），
这是联网检测最大的盲区。只要有一个能走国内出口的代理，把它放进环境变量 ANIYUAN_PROXY，
requests 和无头浏览器就都会走它，等于换成国内的视角去检测。

不设置（默认）就和以前完全一样。代理地址可能带用户名密码，所以只从环境变量读（Actions 里放在 Secrets），
不放进 config.json（仓库是公开的）。
"""
import os
from urllib.parse import unquote, urlparse

ENV = "ANIYUAN_PROXY"


def proxy_url():
    return (os.environ.get(ENV) or "").strip()


def new_session(proxy=None):
    """requests.Session；给了代理就让所有请求都走它。
    requests 里环境变量的代理（HTTPS_PROXY 之类）会盖过 session.proxies，所以此时关掉 trust_env。"""
    import requests
    s = requests.Session()
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})
        s.trust_env = False
    return s


def playwright_proxy(proxy):
    """Playwright 要把服务器地址和用户名密码分开写。"""
    if not proxy:
        return None
    p = urlparse(proxy)
    if not p.hostname:
        return None
    d = {"server": "%s://%s%s" % (p.scheme or "http", p.hostname, (":%d" % p.port) if p.port else "")}
    if p.username:
        d["username"] = unquote(p.username)
    if p.password:
        d["password"] = unquote(p.password)
    return d


def describe(proxy):
    """给日志/报告看的描述（不含密码）。"""
    p = urlparse(proxy or "")
    return "%s://%s%s" % (p.scheme or "http", p.hostname or "?", (":%d" % p.port) if p.port else "") if proxy else ""
