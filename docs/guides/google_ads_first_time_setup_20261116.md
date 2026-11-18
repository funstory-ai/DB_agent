# Google Ads 后台第一次用：KEY 在哪里配（照着点即可）

- 适用：T119 · 账户 `462-389-6831` · 2026-11-16 核对
- 目标：把 Google Ads 数据接进 Databend，最终算**不同渠道的转化率**
- ~~前置结论：助手没有任何凭证，以下全部需要你在浏览器里操作~~ → **2026-11-16 13:45 全部配完并已接入**：Explorer 到手、桌面 OAuth 客户端已建、`refresh_token` 已生成并写入 `config/google-ads.yaml`、API 真实调用成功、`growth.google_ads_daily` 已入库 49 行。下文的逐步操作保留作复现/换账号参考。

### ✅ 13:45 完成状态（实测，非方案）

| 检查 | 结果 |
|---|---|
| `--check` | 凭证可用、API 连通；MCC `4623896831` / 上海书同文网络科技有限公司 / USD / Asia-Shanghai / manager=True |
| `--discover` | 账号树 7 节点、4 个启用子账号（CNY / Asia-Shanghai）、60 个 campaign、v26 字段目录 190/373/177；落 `output/google_ads/discover_20261116.json` |
| `--fetch --write` | 11-09~15 入库 **49 行**（42 中文 + 7 韩语），点击 **5,227 = 用户截图**、展示 35,769、¥10,502.46 CNY |
| 两个额外卡点 | ① 本机代理必须走 `127.0.0.1:7897`（脚本已自动探测）；② MCC 结构必须填 `login_customer_id: "4623896831"`，否则子账号 `PERMISSION_DENIED` |

⚠️ **接入完成 ≠ 转化率算完**：广告侧 campaign 是中文投放名，与我方 `googlekeywords_*` 不是一套，`growth.channel_campaign_map` 仍需人工确认映射；分子/分母/归因窗口未定。详见 T119 任务档「接入完成 → 对最终目标的影响」。

## 进度跟踪（2026-11-16 12:08 用户截图，历史记录）

- 用户已登录 `console.cloud.google.com`，**项目已存在，不必新建**：名称 `My First Project`、项目 ID `sublime-vine-417602`、项目编号 `803076523970`。手册第 1 步可直接跳过「新建项目」，选中这个项目即可。
- ⚠️ 截图顶部有「获享 $300 赠金，开始免费试用」横幅 ⇒ 当前是 **Cloud 免费试用项目**。有第三方报道与 Google 已知问题列表提到 2026-10 起部分免费试用 / 结算被暂停的项目 **Explorer 申请会被自动拒**（非官方确定结论，P043）。若第 5 步申请被拒，先点横幅右侧「**免费开始使用吧**」激活正式结算账号（Google Ads API 调用免费、不扣费），再重新申请。
- ⚠️ 首页快捷按钮里有「**创建 Gemini API 密钥**」——**不要点**，那创建的是 API 密钥，对 Google Ads API 无效；要建的是「OAuth 客户端 ID（桌面应用）」，见第 4 步。
- 当前下一步：顶部搜索框搜 `Google Ads API` → 启用 → 同页概览申请 Explorer。

### 13:03 进度更新：Explorer 已到手（用户截图实测）

用户截图 `Google Ads API 概览页` 显示：

| 项 | 实测值 |
|---|---|
| 当前访问权限级别 | **探索者（Explorer）** ✅ |
| 权益 | 每天 15,000 项操作（测试账号）/ **2,880 次（生产账号）** / 可使用大多数功能含广告系列管理与报告 / **可用于生产用途的环境** |
| 下方「升级访问权限级别」 | 下一个级别＝**基本（Basic）** |

⇒ **第 2 步（启用 API）与第 5 步（申请 Explorer）均已完成**，真实广告账号 `4623896831` 现在可以被查询了。⚠️ **实测纠正上一节的担心**：此前推测「免费试用项目 Explorer 申请可能被自动拒」，本账户**没有发生**，一次就拿到 Explorer。该风险仍作为已知问题保留，但不再是本项目的实际阻塞（P043）。

⚠️ **不要点「升级访问权限级别 → 基本」**：Basic 需要品牌验证，且 Explorer 的 2,880 次/天对本项目拉报表绰绰有余。停在这一页往下走即可。

**当前下一步**＝配 OAuth 同意屏幕 + 建桌面客户端 ID（都在同一个「Google Auth Platform / API 和服务」里，见下下节），目标产物是下载到 `client_secret.json`。

### 13:26 进度更新：OAuth 同意屏幕已创建（用户截图实测）

用户截图为新版 **Google Auth Platform / 概览**页，底部 toast「**已创建 OAuth 配置！**」，左侧菜单为：概览 / **品牌塑造** / **目标对象** / **客户端** / **数据访问** / 验证中心 / 设置（对应官方文档 2026-10 改版后的 Branding / Audience / Clients / Data Access / Verification Center / Settings）。指标卡提示「**您尚未为此项目配置任何 OAuth 客户端**」，右侧有「**创建 OAuth 客户端**」按钮。

⇒ 第 3 步（同意屏幕）已完成；**第 4 步（建桌面客户端）是当前唯一待做的浏览器操作**。

⚠️ 建客户端前先补一个 30 秒检查：点左侧「**目标对象**」→ 若发布状态是「测试 / Testing」，确认「测试用户」里有**自己的 Google 邮箱**，没有就 Add users 加上。跳过这步后面浏览器授权必报 `403 access_denied`。若状态已是「正式发布 / In production」则不需要测试用户。

新版界面点法（对着 13:26 截图）：右侧「**创建 OAuth 客户端**」按钮（或左侧「**客户端**」→「创建客户端」）→ 应用类型选「**桌面应用 / Desktop app**」→ 名称随意 → 创建 → 下载 JSON → 存为 `H:\databend_sql\config\client_secret.json`。

补充：左侧「**数据访问**」里若能添加 `https://www.googleapis.com/auth/adwords` 就加上；搜不到或加不上**直接跳过**，Testing 模式下不影响授权。顶部「免费开始使用吧」横幅仍不要点（Explorer 已到手，无需升级结算）。

### 从 Welcome 首页出发的精确点法（对着 12:08 截图）

1. **点页面顶部中间的搜索框**（写着「搜索 () 资源、文档、产品等」）→ 输入 `Google Ads API` → 回车。
   - 备用走法：左侧「快速访问」里的「**API 和服务**」卡片 → 左侧菜单「**库**」→ 搜索 `Google Ads API`。
2. 结果里点「**Google Ads API**」→ 进入详情页 → 点蓝色「**启用**」。启用后项目立即获得 **Test** 级别。
3. 启用完**不要离开这一页**。页面会显示「API 访问权限级别」；展开「**升级访问权限级别 / Upgrade access level**」→ 确认下一级是 Explorer → 点「**申请访问权限**」。
   - 若找不到该区块，可直达概览页：`console.cloud.google.com/google/ads-apis/overview?project=sublime-vine-417602`
   - 申请前可能需要先完成一次 Google Ads API 的「初始注册」表单（填用途、联系方式），按页面提示填即可。
4. 申请结果截图发我，我再给下一步（配 OAuth 同意屏幕 + 建桌面客户端）。

⚠️ 首页横幅右侧「**免费开始使用吧**」**先不要点**（会引导绑结算/信用卡）。只有第 5 步 Explorer 申请被拒时，才回来点它把项目升级为正式结算账号；Google Ads API 调用免费、不会因此产生费用。

⚠️ 首页快捷操作里的「**创建 Gemini API 密钥**」不要点：那是 API 密钥，不是 OAuth 客户端，对 Google Ads API 无效。

### 已知问题（2026-10 起，官方与第三方一致）

| 现象 | 原因 / 临时处理 |
|---|---|
| Explorer 申请被自动拒，或品牌验证后仍被拒 | 项目处于 **Cloud 免费试用 / 结算账号被暂停或停用** ⇒ 升级到正式结算层级，或换一个已结算的项目申请。**当前 `My First Project` 正是免费试用项目，命中概率较高** |
| 升级到 Explorer/Basic/Standard 后，查真实账号仍报 `AUTHORIZATION_ERROR`，测试账号正常 | Google 已列为已知问题、修复在灰度；官方临时方案＝**新建一个 Cloud 项目**并在新项目里重新申请 Explorer（OAuth 客户端也要建在新项目里，因为访问级别跟项目走） |
| 从旧「API 中心」提交的申请没反应 | 该页面已停用、请求不再处理；必须回到 Cloud 控制台的 Google Ads API「概览」页申请 |

---

## 0. 先分清两个网站（第一次用最容易卡在这里）

| 网站 | 网址 | 作用 | 配 KEY 吗 |
|------|------|------|-----------|
| **Google Ads 后台**（你截图的那个） | `ads.google.com` | 看数据、导出 CSV、拿客户 ID、给账号加权限 | ❌ **不配** |
| **Google Cloud 控制台** | `console.cloud.google.com` | 建项目、启用 API、生成 OAuth 客户端、申请访问级别 | ✅ **全部在这里** |

**KEY 一个都不在 Google Ads 后台里。** 网上大量教程教的「Google Ads 后台 → 工具与设置 → API 中心 → 申请 22 位开发者令牌」已经作废：2026-09-09 起 developer token 停用，访问权限改挂在 **Google Cloud 项目**上。别再去后台找「API 中心」「开发者令牌」，找不到的。

> 另一个高频走错：在 Cloud 控制台「凭据」页创建的是 **OAuth 客户端 ID**，不是「API 密钥」。创建「API 密钥」对 Google Ads API 没用。

---

## 1. 一共要配 4 样东西（一一对应，别混）

| # | 名称 | 从哪来 | 落到哪 |
|---|------|--------|--------|
| 1 | `client_id` + `client_secret` | Cloud 控制台建 **OAuth 客户端 ID（桌面应用）** → 下载 JSON | `config/google-ads.yaml` 第 1、2 行 |
| 2 | `refresh_token` | 本地跑一条命令、浏览器授权一次后生成 | 同一文件第 3 行 |
| 3 | **Explorer 访问级别** | Cloud 控制台「Google Ads API 概览」页申请 | 云端状态，**不填文件** |
| 4 | `login_customer_id` | 仅当通过 MCC 经理账号访问时才需要 | 同一文件，注释掉即可 |

不需要 `developer_token`。`use_proto_plus: true` 必须保留。

---

## 2. 逐步操作

### 第 1 步：登录 Cloud 控制台并新建项目

1. 打开 `console.cloud.google.com`，用**对广告账号 `462-389-6831` 有读权限的 Google 账号**登录。
2. 顶部「选择项目」→「新建项目」→ 名称填 `ads-sync`（随意）→「创建」→ 回到顶部选中这个项目。
3. 如提示绑定结算账号，按提示绑。**Google Ads API 调用本身免费**，但 Cloud 项目受标准配额约束。

### 第 2 步：启用 Google Ads API

左侧菜单「**API 和服务 → 库**」→ 搜索 `Google Ads API` → 点「**启用**」。

### 第 3 步：配 OAuth 同意屏幕（+ 把自己加为测试用户）

> 2026-10 起 Cloud 控制台把这一块改版成「**Google Auth Platform**」，拆成 Branding / Audience / Data Access / Clients 四段；老界面仍叫「OAuth 同意屏幕」。两套名字都列在下面，看到哪个用哪个。

| 新版「Google Auth Platform」 | 老版「API 和服务 → OAuth 同意屏幕」 |
|---|---|
| Overview → **Get Started**，填 App name、User support email | 用户类型选 **External** → 创建 |
| Audience 选 **External**（公司内部 Workspace 组织才选 Internal） | 填应用名称、支持邮箱、开发者邮箱 |
| Contact Information 填自己邮箱 → 勾选用户数据政策 → Create | 一路 Save and Continue |
| Data Access → Add or Remove Scopes → 加 `https://www.googleapis.com/auth/adwords` | Scopes 页同样加该 scope |
| **Audience → Test users → Add users → 填你自己的 Google 邮箱** | **测试用户 → Add users → 填自己邮箱** |

⚠️ **不加测试用户，第 7 步授权必报 403 `access_denied`**，这是第一次配最常见的失败点。

⚠️ 发布状态停在 **Testing** 时，`refresh_token` **7 天过期**。先跑通验证完全够用；要长期每日同步，需要把状态改成 **In production**（External + 敏感 scope 可能触发 Google 应用验证；若是公司内部 Workspace，选 Internal 可免验证）。过期了重跑一次第 7 步即可。

### 第 4 步：创建 OAuth 客户端 ID（拿 `client_id` / `client_secret`）

- 新版：「Google Auth Platform → **Clients** → **Create Client**」
- 老版：「API 和服务 → **凭据** → **创建凭据** → **OAuth 客户端 ID**」

应用类型选 **「桌面应用 / Desktop app」**（选「Web 应用」会多要回调 URI，脚本用不上），名称随意 → 创建 → 弹窗显示 Client ID 和 Client secret → 点**下载 JSON**，存成：

```
H:\databend_sql\config\client_secret.json
```

该文件名已被 `.gitignore` 的 `config/*client_secret*.json` 排除，不会进版本库。

### 第 5 步：申请 Explorer 访问级别

回到 Cloud 控制台「**Google Ads API 概览**」页（API 和服务 → 库 → Google Ads API → 管理 / 概览）：

1. 确认当前访问级别显示为 **Test**；
2. 展开「**升级访问权限级别 / Upgrade access level**」；
3. 确认下一级别是 **Explorer** → 点「**申请访问权限**」。

多数情况自动批准。⚠️ 只停在 Test 级时，查真实账号会报 `CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION`（Test 只能查测试账号）。2026-10 起有已知问题：Cloud 免费试用项目、结算被暂停/停用的项目可能被自动拒；被拒就先走第 9 节的 CSV 路径，别卡在这里。

### 第 6 步：确认 Google Ads 后台的 3 件事（这里仍不配 KEY）

在 `ads.google.com`：

| 要确认 | 位置 | 本项目值 |
|---|---|---|
| 客户 ID | 右上角头像下方 / 帮助菜单底部 | `462-389-6831` → API 用 `4623896831`（脚本已写死） |
| 账号权限 | 工具与设置 → 访问和安全 / 账号访问权限 | 授权用的 Google 账号至少 **Read-only** |
| 账户时区 / 币种 | 工具与设置 → 账号设置 / 偏好设置 | 也可由 `--discover` 直接读出；⚠️ 账户时区 ≠ 北京日，跨表对比要先对齐 |

### 第 7 步：生成 `refresh_token`（本地一条命令，会开浏览器）

```bash
cd /h/databend_sql
F:/python312/python.exe scripts/fetch_google_ads_api.py --make-refresh-token --client-secret config/client_secret.json
```

浏览器会打开 → 登录**有广告账号读权限的 Google 账号** → 授权 → 终端打印出可直接粘贴的 3 行（`client_id` / `client_secret` / `refresh_token`）。

- 若提示「Google 尚未验证此应用」，Testing 模式下属正常，点「继续 / Advanced → Go to」。
- ⚠️ scope `https://www.googleapis.com/auth/adwords` **不是只读权限**，别用超管主账号授权，建议给一个只读的 Google Ads 用户。

### 第 8 步：填配置文件

```bash
cd /h/databend_sql
cp config/google-ads.yaml.example config/google-ads.yaml
```

把第 7 步打印的 3 个值替换掉占位符，最终长这样：

```yaml
client_id: "xxxxxxxxxx.apps.googleusercontent.com"
client_secret: "GOCSPX-xxxxxxxxxx"
refresh_token: "1//0xxxxxxxxxx"
# login_customer_id: "1234567890"   # 仅 MCC 访问时取消注释
use_proto_plus: true
```

`config/google-ads.yaml` 已被 `.gitignore` 排除。**不要把凭证贴进聊天或提交到 git**；填好文件告诉我一声即可。

### 第 9 步：验证并灌库

```bash
F:/python312/python.exe scripts/fetch_google_ads_api.py --check      # 连通 + 币种/时区/campaign 数
F:/python312/python.exe scripts/fetch_google_ads_api.py --discover   # 枚举账户实际有的数据 → output/google_ads/discover_*.json
F:/python312/python.exe scripts/fetch_google_ads_api.py --fetch       # 干跑对账（11-09~15）
F:/python312/python.exe scripts/fetch_google_ads_api.py --fetch --write  # 写入 growth.google_ads_daily
```

验收标准：`SELECT count(*) FROM growth.google_ads_daily` > 0，且 discover JSON 存在。

**暂时不想配 KEY 的最短路径**：Google Ads 后台 → 报告/概览 → 右上角「下载」→ CSV，选 11-09~15、细分「天」、**加上「广告系列」列**，放 `output/google_ads/`，我用 `scripts/ingest_google_ads_csv.py` 立刻入库对账。但这是一次性搬运，长期每日同步仍需 API。

---

## 3. 常见报错对照

| 报错 / 现象 | 原因 | 处理 |
|---|---|---|
| `403 access_denied` / 「应用已被阻止」 | 没把自己加进 OAuth 测试用户 | 回第 3 步 Audience → Test users |
| `CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION` | 项目还是 Test 级 | 回第 5 步申请 Explorer |
| `NOT_ADS_USER` | 授权的 Google 账号不是 Ads 用户；或用了服务账号但没 Workspace 域委派 | 改用桌面 OAuth + 有读权限的账号 |
| `PERMISSION_DENIED` / `CUSTOMER_NOT_FOUND` | 客户 ID 带横线 / 账号没读权限 | 用 `4623896831`，确认只读权限 |
| `invalid_grant` / token expired | Testing 模式 refresh_token 7 天过期 | 重跑第 7 步 |
| `login_customer_id` required / `PERMISSION_DENIED: manager's customer id must be set in login-customer-id header` | **本项目必现**：`4623896831` 是 MCC 经理账号，自身 campaign=0，数据在子账号 | `config/google-ads.yaml` 填 `login_customer_id: "4623896831"`（模板已默认填好），脚本会自动遍历启用子账号 |
| `ProxyError: Tunnel connection failed: 502 Bad Gateway` / `ConnectTimeout` | 环境注入的代理 `127.0.0.1:59139` 不通、直连被墙，**只有系统代理 127.0.0.1:7897 通** | 脚本已内置 `setup_network()` 自动探测；必要时显式 `--proxy http://127.0.0.1:7897`。浏览器授权成功后仍报这个错＝卡在换 token，重跑一次授权即可 |
| `invalid_client` / `401` | client_id、client_secret 粘错，或客户端建成了「Web 应用」 | 重建**桌面应用**类型客户端 |
| `--check` 显示 `广告系列数: 0` | 查的是 MCC 自身，不是子账号 | 正常现象；看 `--check` 输出的 4 个启用子账号清单，或 `--discover` 的账号树 |

---

## 4. 配好之后怎么走到「算转化」（主线，别歪）

`--discover` 拿到**账户真实**的 campaign 清单 → 人工填 `growth.channel_campaign_map`（把 Ads 侧 campaign 名映射到我方 `googlekeywords_*` UTM 名，P045 禁止猜值）→ 跑 `sql/reports/query_google_ads_channel_conversion_20261116.sql` 的 Q0~Q5 → 按「campaign × 日」产出点击/花费/CPA/CVR。

分子/分母/归因窗口仍待业务确认：候选是分母＝带渠道标记的新装设备、分子＝7 天内付费单（经 `deviceid → userid` 桥接），并给 3/7/14 天窗口的敏感性对照。2024 年历史 CSV 的口径（install 作分母、30 天内订阅作分子）只能作候选，不能直接当 2026 定案（P025/P044）。
