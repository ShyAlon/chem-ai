from collections import OrderedDict
from ipaddress import IPv6Address, ip_address
from math import ceil


def client_key(peer: str | None, proxy_address: str | None = None) -> str:
    for address in (proxy_address, peer):
        if address:
            try:
                ip = ip_address(address)
            except ValueError:
                continue
            if isinstance(ip, IPv6Address):
                return str(ip.ipv4_mapped or IPv6Address(int(ip)))
            return str(ip)
    return "unknown"


class QuestionCooldown:
    def __init__(self, seconds: int = 10):
        self.seconds = seconds
        self.accepted: OrderedDict[str, float] = OrderedDict()

    def take(self, key: str, now: float) -> int | None:
        if self.seconds <= 0:
            return None
        while self.accepted and next(iter(self.accepted.values())) <= now - self.seconds:
            self.accepted.popitem(last=False)
        if key in self.accepted:
            return ceil(self.accepted[key] + self.seconds - now)
        self.accepted[key] = now
        return None
