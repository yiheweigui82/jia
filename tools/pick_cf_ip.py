#!/usr/bin/env python3
"""重新优选 Cloudflare 入口 IP（CN 直连实测）。

用途：sub.txt 里各节点的「连接地址」默认取 check.yml 的 EDT_ADDR（优选IP）。
优选IP 会随时间/运营商变化失效，觉得慢了就在这里重测一次，把 TOP3 填回 EDT_ADDR。

原理：用 curl --resolve 把域名钉到候选 IP 上（SNI/Host 仍是你的入口域名），
所以测出来的就是「客户端经由这个 IP 摸到本 Worker」的真实耗时。判定可用还需
返回 200 且页面大小等于入口的伪装页大小（防止把 CF 的错误页/别的产品页当候选）。

用法（必须关掉代理，否则测的是代理的中转速度，不是 CN 直连）：
    python tools/pick_cf_ip.py
    python tools/pick_cf_ip.py --host jia.baozi.kdns.fr --rounds 3
"""
import argparse
import concurrent.futures as cf
import subprocess

# CF anycast 常见段的代表 IP（每个段扫几个，够用且快）
CANDIDATES = [f"104.{a}.{b}.1" for a in (16, 17, 18, 19, 20, 21, 22, 24, 25, 26, 27)
              for b in (0, 64, 128, 192)]
CANDIDATES += [f"172.{a}.{b}.1" for a in (64, 65, 66, 67, 68, 69, 70, 71) for b in (0, 128)]
CANDIDATES += ["162.158.0.1", "162.159.0.1", "188.114.96.1", "190.93.240.1", "197.234.240.1",
               "198.41.128.1", "141.101.64.1", "108.162.192.1", "173.245.48.1", "103.21.244.1",
               "103.22.200.1", "131.0.72.1"]


def decoy_size(host):
    """入口根路径的伪装页大小，用作「这个 IP 确实服务本 Worker」的判据。"""
    r = subprocess.run(["curl.exe", "--noproxy", "*", "-s", "-o", "NUL", "-m", "10",
                        "-w", "%{http_code} %{size_download}", f"https://{host}/"],
                       capture_output=True, text=True)
    code, _, size = (r.stdout or "").strip().partition(" ")
    return size.strip() if code == "200" else ""


def probe(ip, host, want_size):
    r = subprocess.run(["curl.exe", "--noproxy", "*", "-s", "-o", "NUL", "-m", "6",
                        "--resolve", f"{host}:443:{ip}", "-w",
                        "%{time_connect}|%{time_appconnect}|%{time_total}|%{http_code}|%{size_download}",
                        f"https://{host}/"], capture_output=True, text=True)
    p = (r.stdout or "").strip().split("|")
    if len(p) != 5 or p[3] != "200" or (want_size and p[4] != want_size):
        return None
    return {"ip": ip, "tcp": round(float(p[0]) * 1000),
            "tls": round(float(p[1]) * 1000), "ttfb": round(float(p[2]) * 1000)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="jia.baozi.kdns.fr", help="你的 edgetunnel 入口域名")
    ap.add_argument("--rounds", type=int, default=2, help="测几轮取每 IP 最优值")
    ap.add_argument("--top", type=int, default=3, help="输出前几名")
    args = ap.parse_args()

    want = decoy_size(args.host)
    print("host=%s  伪装页大小=%s  候选=%d 个" % (args.host, want or "(未取到, 放宽判据)", len(CANDIDATES)))

    best = {}
    for rnd in range(1, args.rounds + 1):
        with cf.ThreadPoolExecutor(max_workers=16) as ex:
            for res in ex.map(lambda ip: probe(ip, args.host, want), CANDIDATES):
                if res and (res["ip"] not in best or res["tls"] < best[res["ip"]]["tls"]):
                    best[res["ip"]] = res
        print("第 %d 轮完成, 累计可用 %d" % (rnd, len(best)))

    ranked = sorted(best.values(), key=lambda x: (x["tls"], x["tcp"]))
    print("\n%-18s %8s %8s %8s" % ("IP", "tcp_ms", "tls_ms", "ttfb_ms"))
    for r in ranked[:max(args.top, 12)]:
        print("%-18s %8d %8d %8d" % (r["ip"], r["tcp"], r["tls"], r["ttfb"]))
    top = ",".join(r["ip"] for r in ranked[:args.top])
    print("\n可用 %d / 候选 %d" % (len(best), len(CANDIDATES)))
    print("把下面这行填进 .github/workflows/check.yml 的 EDT_ADDR：")
    print("          EDT_ADDR: \"%s\"" % top)


if __name__ == "__main__":
    main()
