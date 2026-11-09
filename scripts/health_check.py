import json
import socket
import ssl
import sys
import time
from datetime import datetime, timezone, timedelta

TARGETS = [
    {"name": "Cloady US-West (USW1)", "host": "xray-node-sb1ilsor-workspace-83goto.cloady.io", "port": 443, "required": True},
    {"name": "Cloady US-East (USE1)", "host": "xray-node-use1-w8suq6p8-workspace-83goto.cloady.io", "port": 443, "required": True},
    {"name": "EdgeTunnel entry", "host": "vitao.de5.net", "port": 443, "required": True},
    {"name": "Komari panel", "host": "komari.vitao.de5.net", "port": 443, "required": True},
    {"name": "Home broadband line", "host": "home.vitao.de5.net", "port": 443, "required": False},
]

CF_ORIGIN_DOWN = {520, 521, 522, 523, 524, 525, 526, 527}


def check(t):
    host, port = t["host"], t["port"]
    start = time.time()
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as s:
                s.settimeout(10)
                s.sendall(f"GET / HTTP/1.0\r\nHost: {host}\r\nUser-Agent: actions-health-check\r\n\r\n".encode())
                data = s.recv(4096).decode("utf-8", "replace")
        ms = int((time.time() - start) * 1000)
        first = data.splitlines()[0] if data.splitlines() else ""
        status = None
        parts = first.split(" ")
        if len(parts) >= 2 and parts[1].isdigit():
            status = int(parts[1])
        if status is None:
            return {**t, "alive": False, "detail": f"no HTTP status line ({first[:60]})", "ms": ms}
        if status in CF_ORIGIN_DOWN:
            return {**t, "alive": False, "detail": f"HTTP {status} (Cloudflare origin unreachable)", "ms": ms}
        return {**t, "alive": True, "detail": f"HTTP {status}", "ms": ms}
    except Exception as e:
        ms = int((time.time() - start) * 1000)
        return {**t, "alive": False, "detail": f"{type(e).__name__}: {e}", "ms": ms}


def main():
    now_utc = datetime.now(timezone.utc)
    now_cst = now_utc.astimezone(timezone(timedelta(hours=8)))
    results = [check(t) for t in TARGETS]
    required_failed = [r for r in results if r["required"] and not r["alive"]]

    lines = []
    lines.append("# Node health status")
    lines.append("")
    lines.append(f"Last check: {now_cst.strftime('%Y-%m-%d %H:%M')} CST ({now_utc.strftime('%Y-%m-%d %H:%M')} UTC) by GitHub Actions")
    lines.append("")
    lines.append("| Target | Host | Result | Latency | Detail |")
    lines.append("| --- | --- | --- | --- | --- |")
    for r in results:
        mark = "OK" if r["alive"] else ("DOWN (info only)" if not r["required"] else "DOWN")
        lines.append(f"| {r['name']} | {r['host']}:{r['port']} | {mark} | {r['ms']} ms | {r['detail']} |")
    lines.append("")
    lines.append(f"Required targets down: {len(required_failed)}")
    report = "\n".join(lines) + "\n"

    with open("health/status.md", "w", encoding="utf-8") as f:
        f.write(report)
    print(report)

    summary_path = None
    import os
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(report)

    sys.exit(1 if required_failed else 0)


if __name__ == "__main__":
    main()
