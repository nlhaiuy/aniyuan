"""域名工具：主机名、主域名、主域名的名字部分（girigirilove.com / girigirilove.xyz 是同一个站）。"""
from urllib.parse import urlparse

SECOND_LEVEL = {"com", "net", "org", "co", "gov", "edu", "ac"}


def host_of(url):
    return (urlparse(url).netloc or "").lower().split(":")[0]


def registrable(host):
    """主域名：example.com / example.co.jp（没引入公共后缀库，用常见规则估计）。"""
    parts = [p for p in host.split(".") if p]
    if len(parts) <= 2:
        return ".".join(parts)
    if len(parts[-1]) == 2 and parts[-2] in SECOND_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def sld(host):
    """主域名的名字部分：girigirilove.com -> girigirilove。"""
    reg = registrable(host)
    return reg.split(".")[0] if reg else ""
