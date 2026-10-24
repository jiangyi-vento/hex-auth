import ipaddress

from fastapi import Request


def get_client_ip(request: Request) -> str:
    """
    获取客户端真实IP。

    生产部署在 Nginx 之后，优先取 X-Real-IP（由 Nginx 用 $remote_addr 覆盖写入，
    不可被客户端伪造）；X-Forwarded-For 的首个元素可能是客户端伪造的，仅作兜底。

    所有候选值必须通过 IP 格式校验才会被采用——防止伪造的超长字符串撑爆
    ip_address 列（1406 Data too long，与 private_key 同族问题），也避免垃圾值
    污染限流与审计。全部候选非法时回退到直连地址，最终兜底 "unknown"。
    """
    candidates = [
        request.headers.get("X-Real-IP"),
        request.headers.get("X-Forwarded-For", "").split(",")[0] or None,
        request.client.host if request.client else None,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        candidate = candidate.strip()
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return "unknown"
