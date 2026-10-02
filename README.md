# jia · VPN Gate SSTP 节点检测

自动检测 **VPN Gate 公共中继**的 SSTP（TCP 入口）可用性，每 30 分钟刷新一次，
结果发布在 GitHub Pages 上。

## 在线使用（推荐）

直接用浏览器打开，无需安装任何东西：

- 🌐 **节点列表页**：<https://yiheweigui82.github.io/jia/>
- 📄 原始数据（JSON）：<https://yiheweigui82.github.io/jia/data.json>
- 📋 edgetunnel 链式代理清单：<https://yiheweigui82.github.io/jia/chains.txt>
- 📋 edgetunnel 自定义优选 IP 清单：<https://yiheweigui82.github.io/jia/hosts.txt>
- 📋 edgetunnel 完整 vless 订阅：<https://yiheweigui82.github.io/jia/sub.txt>

页面上点任意 `host:port` 即可复制对应的 `sstp://vpn:vpn@host:port` 链接。

## 它做了什么

```
VPN Gate 官方 API (失败时回退 GitHub 镜像)
        ↓ 只保留带 TCP 入口的中继 = SSTP 可用节点, 并按 host+port 去重
Cloudflare Worker 并发检测 (32 并发)
        ↓ 只保留 success=true 的节点, 按国家分组、住宅优先、延迟升序
public/data.json + public/index.html → GitHub Pages
```

判定逻辑写死为「绝不允许假成功」：数据源全挂 / 解析不出任何节点 / Worker 完全不可达，
脚本直接以退出码 1 结束，不生成空结果。

## 自动运行

`.github/workflows/check.yml` 通过 GitHub Actions 运行：

- 每 30 分钟定时执行一次（cron 为 UTC 时间）
- 也可在仓库 **Actions → VPN Gate Node Check → Run workflow** 手动触发
- 推送到 `main` 分支会立即触发一次

每次运行会重新生成 `public/` 下的全部文件并部署到 GitHub Pages。

## 本地运行（可选）

```bash
pip install -r requirements.txt
python vpngate.py
# 产物在 public/ 目录: data.json / index.html / chains.txt / hosts.txt / sub.txt
```

可用环境变量覆盖默认配置：

| 变量 | 说明 |
|---|---|
| `VPNGATE_API` | VPN Gate 官方数据源 |
| `VPNGATE_MIRROR` | 官方源失败时的回退镜像 |
| `CHECK_WORKER` | 检测用 Cloudflare Worker 地址 |
| `CHECK_CONCURRENCY` | 并发数（默认 32） |
| `CHECK_TIMEOUT` | 单请求超时秒数（默认 90） |
| `MAX_CHECK_NODES` | 只检测前 N 个节点（0 = 不限，调试用） |
| `EDGE_HOSTS` / `HOSTS_ENTRY` | edgetunnel 入口地址池 |

## 文件说明

| 路径 | 作用 |
|---|---|
| `vpngate.py` | 主程序：取节点 → 筛 SSTP → Worker 检测 → 生成网页与清单 |
| `web/index.html` | 网页模板（运行时复制到 `public/index.html`） |
| `.github/workflows/check.yml` | GitHub Actions 定时检测 + Pages 部署 |
| `public/` | **运行时生成，不入库**（见 `.gitignore`） |

## 说明

- 节点来自 [VPN Gate](https://www.vpngate.net/)（日本筑波大学学术项目）的公开中继列表。
- 「住宅 / 数据中心」为基于中继注册类型与出口运营商的**估算**，非严格判定。
- `chains.txt` / `hosts.txt` / `sub.txt` 供 edgetunnel 使用，账号密码固定 `vpn:vpn`；
  名字固定、只有节点地址每 30 分钟自动更换。`sub.txt` 里的节点域名与 UUID 可通过
  环境变量 `EDT_DOMAIN` / `EDT_UUID` 换成自己的部署。
