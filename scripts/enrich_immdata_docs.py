"""Enrich immdata core table docs with probed metadata (manual sections)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMM = ROOT / "docs" / "tables" / "immdata"

# 仅替换「来源与用途」区块：从标题到下一个 ## 或 AUTO schema
ENRICH: dict[str, str] = {
    "user_behaviour": """## 来源与用途（手工维护）

- **数据来源**：沉浸式翻译插件/客户端埋点行为流（最细粒度事件表）
- **同步方式**：持续写入；体量极大（百亿级），查询必须带时间与事件过滤
- **更新频率**：近实时
- **业务含义**：插件侧行为真相源：翻译页、浮球、字幕、弹窗、限额等
- **建议粒度**：`device_id` × `event_name` × `created_ts`（事件行）
- **主键 / 唯一键**：无业务主键；勿对全表 `COUNT(*)` / 无过滤扫描
- **常用过滤**：`created_ts` 时间窗；按需 `event_name`、`platform_type`、`install_from`、`user_type`
- **关联建议**：与注册用户关联需经设备/账号映射，本表本身以 `device_id` 为主，**无稳定 userid 字段**
- **勿想当然**：
  - `install_day` 可能出现 `1970-01-01`（占位），不能当真实安装日
  - `user_type` 含 `anonymous` / `free` / 会员档位等，口径需先对齐业务
  - `platform_type` 除 desktop/mobile/tablet 外，可能混入 iPhone 机型字符串
  - `ex_char_arg*` / `ex_int_arg*` 含义随 `event_name` 变化，必须查表文档或埋点说明
  - 存在拼写异常事件名如 `translage_page_daily`
""",
    "user_access_log": """## 来源与用途（手工维护）

- **数据来源**：插件访问/性能类埋点（结构近似 `user_behaviour`，另含 `url`/`site`）
- **同步方式**：持续写入；十亿级，必须限时限事件
- **更新频率**：近实时
- **业务含义**：页面访问、performance 等；带完整 URL
- **建议粒度**：事件行（`device_id` × `created_ts`）
- **主键 / 唯一键**：无
- **常用过滤**：`created_ts`；`event_name`（如 `performance`）
- **关联建议**：同 behaviour，以 `device_id` 为主
- **勿想当然**：不要与 `user_behaviour` 混为一谈；字段高度相似但用途与事件集合不同
""",
    "imt_userinfo": """## 来源与用途（手工维护）

- **数据来源**：业务库用户表同步（IMT 账号体系）
- **同步方式**：业务库 → Databend（`imt_*` 前缀）
- **更新频率**：随业务同步（约 2023-08 起有数据）
- **业务含义**：注册用户主档：邮箱、openid、账号类型等
- **建议粒度**：用户一行（`id`）
- **主键 / 唯一键**：`id`；另有 `uid`（勿与 `id` 混用，关联前先核对）
- **常用过滤**：`COALESCE(isdeleted,0)=0`（存在少量软删）
- **关联建议**：订单/设备多用 `userid` 指向本表 `id`（仍需在具体表文档确认）
- **勿想当然**：
  - `accounttype`：`normal` / `oauth` / `api_key`
  - `platform` 大量为空或 `''`，`cn` 表示国内相关渠道，不可当操作系统
""",
    "imt_deviceinfo": """## 来源与用途（手工维护）

- **数据来源**：业务库设备表同步
- **同步方式**：业务库 → Databend
- **更新频率**：随业务同步
- **业务含义**：设备维度安装/登录信息，含 UTM、安装渠道、浏览器等
- **建议粒度**：设备一行（`id`）；业务键常看 `deviceid` + `userid`
- **主键 / 唯一键**：`id`；`deviceid` 可能一对多历史，关联前先核对
- **常用过滤**：`COALESCE(isdeleted,0)=0`
- **关联建议**：`userid` → `imt_userinfo.id`；埋点 `device_id` ↔ 本表 `deviceid`（编码格式需抽样确认是否一致）
- **勿想当然**：`installchannel` 主流为 chrome_store / edge_store / firefox_store / safari 等；存在 `dev` 渠道
""",
    "imt_subscriptiongoodsorder": """## 来源与用途（手工维护）

- **数据来源**：业务库订阅商品订单
- **同步方式**：业务库 → Databend
- **更新频率**：随支付 webhook / 业务同步
- **业务含义**：订阅订单明细（Stripe/各渠道成交记录）
- **建议粒度**：订单行（`id`）
- **主键 / 唯一键**：`id`
- **常用过滤**：`COALESCE(isdeleted,0)=0`；有效成交常见 `orderstatus='finished'`（另有 `refunded`）
- **关联建议**：`userid` → `imt_userinfo.id`；与 checkout 经 `checkoutsessionid` 等关联
- **勿想当然**：
  - `finished` ≠ 一定付费成功现金流入：试用单等需结合 `ordertype` / `amountpaid` / 清洗表标志位
  - `amount` 与 `amountpaid` 单位/币种可能不同（`amount` 多为标价小数，`amountpaid` 常见最小货币单位整数）
  - 分析付费优先考虑清洗表 `dwd_order_clean` 的 `is_paid_order` 等标志
""",
    "imt_checkoutsession": """## 来源与用途（手工维护）

- **数据来源**：业务库结账会话（Checkout Session）
- **同步方式**：业务库 → Databend
- **更新频率**：随下单流程同步
- **业务含义**：发起支付/试用的会话；含 Stripe/Google Play/iOS 等字段
- **建议粒度**：会话行（`id`）；业务键常看 `checkoutsessionid`
- **主键 / 唯一键**：`id`
- **常用过滤**：`COALESCE(isdeleted,0)=0`；`orderstatus` 含 `created`/`finished` 等
- **关联建议**：`userid` → 用户；下游订单、`imt_subscriptionordersource.checkoutsessiontableid`
- **勿想当然**：会话 `created` 很多未支付；不要把 checkout 数当付费数
""",
    "imt_subscriptionordersource": """## 来源与用途（手工维护）

- **数据来源**：业务库订单来源/归因快照
- **同步方式**：业务库 → Databend
- **更新频率**：随 checkout/下单
- **业务含义**：下单时的设备、UTM、AB、是否试用等归因信息
- **建议粒度**：来源行；经 `checkoutsessiontableid` 关联 checkout
- **主键 / 唯一键**：`id`
- **常用过滤**：`COALESCE(isdeleted,0)=0`
- **关联建议**：`checkoutsessiontableid` → `imt_checkoutsession.id`；`userid` → 用户；`deviceid` → 设备
- **勿想当然**：`extenddata` JSON 内可能有 `orderFrom` / `abField`，解析前先抽样
""",
    "imt_campaigninfo": """## 来源与用途（手工维护）

- **数据来源**：业务库活动/落地归因信息（设备侧）
- **同步方式**：业务库 → Databend
- **更新频率**：随访问/转化上报
- **业务含义**：设备维度 campaign / UTM / reference
- **建议粒度**：记录行（`deviceid` 可多条）
- **主键 / 唯一键**：`id`
- **常用过滤**：`COALESCE(isdeleted,0)=0`
- **关联建议**：`deviceid`；勿直接当「安装唯一归因」除非已去重规则
- **勿想当然**：空 UTM 很常见；`translated=1` 不代表付费
""",
    "imt_open_id": """## 来源与用途（手工维护）

- **数据来源**：第三方登录 OpenID 绑定（Google / 微信等）
- **同步方式**：业务库 → Databend
- **更新频率**：随 OAuth
- **业务含义**：`uid` 与外部 `app_open_id` 映射
- **建议粒度**：绑定行
- **主键 / 唯一键**：`id`；业务上关注 `(app_name, uid)` / open_id
- **常用过滤**：按 `app_name`（如 Google、CNWeChatWeb）
- **关联建议**：`uid` 与 `imt_userinfo` 的 `id`/`uid` 对齐方式需抽样确认，**禁止想当然**
- **勿想当然**：含 token 类字段，分析时不要选出敏感列到本地宽表
""",
    "imt_oauth_open_user": """## 来源与用途（手工维护）

- **数据来源**：OAuth 开放用户映射（如 imt-web）
- **同步方式**：业务库 → Databend
- **业务含义**：`client_id` + `open_id`/`subject` → `uid`
- **建议粒度**：映射行
- **主键 / 唯一键**：关注 `uid` / `open_id`
- **常用过滤**：按 `client_id`
- **关联建议**：`uid` → 用户体系；与埋点 device 无直接键
- **勿想当然**：与 `imt_open_id` 不是同一张表
""",
    "dwd_order_clean": """## 来源与用途（手工维护）

- **数据来源**：由 checkout + 订单等清洗得到的分析宽表（DWD）
- **同步方式**：ETL 产出（非原始业务表）
- **更新频率**：随 ETL（以表内 `order_day`/`checkout_day` 为准）
- **业务含义**：统一订单分析口径，带 `is_*` 标志位
- **建议粒度**：订单/会话分析行（含 `user_id`）
- **主键 / 唯一键**：常见用 `order_id` / `checkoutsessionid`（先确认是否唯一）
- **常用过滤**：
  - 付费：`is_paid_order=1`
  - 有效单：`is_valid_order=1`
  - 试用：`is_trial_order=1`
  - 会员相关：`is_membership_order=1`
- **关联建议**：`user_id` → `imt_userinfo.id`；首单画像见 `dws_order_user_firsts`
- **勿想当然**：优先用本表标志位，而不是只看原始 `orderstatus='finished'`
""",
    "dws_order_user_firsts": """## 来源与用途（手工维护）

- **数据来源**：订单域用户首次行为汇总（DWS）
- **同步方式**：ETL
- **业务含义**：用户首次 checkout / 试用 / 付费时间及对应套餐渠道
- **建议粒度**：`user_id` 一行
- **主键 / 唯一键**：`user_id`（预期唯一）
- **常用过滤**：`has_paid` / `has_trial` / `has_checkout`
- **关联建议**：`user_id` → `imt_userinfo.id`
- **勿想当然**：`has_trial=1` 且 `has_paid=0` 表示试用未转付费（截至汇总时点）
""",
    "dwd_behaviour": """## 来源与用途（手工维护）

- **数据来源**：`user_behaviour` 的裁剪/清洗子集（字段更少，含 `dt`、`user_id`）
- **同步方式**：ETL；行数远小于原始 behaviour，但仍需按 `dt` 过滤
- **业务含义**：分析用行为明细；`user_id` 可能为空（匿名）
- **建议粒度**：事件行；按 `dt` 分区思维查询
- **主键 / 唯一键**：无
- **常用过滤**：`dt`；`event_name`
- **关联建议**：有 `user_id` 时可关联用户；否则用 `device_id`
- **勿想当然**：不是全量 `user_behaviour`；覆盖事件/时间范围需先核 min/max(`dt`)
""",
    "user_translate_day": """## 来源与用途（手工维护）

- **数据来源**：翻译行为按日汇总
- **同步方式**：ETL
- **业务含义**：用户每日翻译次数
- **建议粒度**：`dt` × `userid`
- **主键 / 唯一键**：预期 (`dt`,`userid`)
- **常用过滤**：日期范围
- **关联建议**：注意 **`userid` 类型为 VARCHAR**，与其它表 BIGINT 关联时需显式转换
- **勿想当然**：勿与 `user_translate_attr_day`（多维拆分）直接等价加总而不核对口径
""",
    "user_translate_hour": """## 来源与用途（手工维护）

- **数据来源**：翻译行为按小时汇总
- **同步方式**：ETL
- **业务含义**：`hour_ts_utc` × 用户翻译次数（时间戳为 UTC）
- **建议粒度**：小时 × `userid`（BIGINT）
- **主键 / 唯一键**：预期 (`hour_ts_utc`,`userid`)
- **常用过滤**：时间窗（注意 UTC vs 北京时间）
- **关联建议**：`userid` → 用户 id
- **勿想当然**：与日表时区不一致时会导致对不齐
""",
    "user_translate_attr_day": """## 来源与用途（手工维护）

- **数据来源**：翻译行为按日 + 属性维度汇总
- **同步方式**：ETL
- **业务含义**：平台/浏览器/OS/目标语言等维度下的翻译次数
- **建议粒度**：`dt` × `userid` × 属性维
- **主键 / 唯一键**：多维组合键
- **常用过滤**：`dt`；维度枚举
- **关联建议**：`userid` BIGINT
- **勿想当然**：同一用户一天多行；`SUM(translate_cnt)` 按维展开，不要与日表不加区分直接对比
""",
    "user_domain_tag_day": """## 来源与用途（手工维护）

- **数据来源**：`translate_page.ex_char_arg9=domain_tag_group` 汇总；表注释称上报率约 1.76%
- **同步方式**：ETL
- **业务含义**：用户每日域名标签翻译次数（research/dev/collab 等）
- **建议粒度**：`dt` × `userid`
- **主键 / 唯一键**：预期 (`dt`,`userid`)
- **常用过滤**：日期；只作正向信号（低上报率）
- **关联建议**：`userid` → 用户
- **勿想当然**：**不能**外推为全体用户域名偏好；未上报用户缺失
""",
    "user_page_content_day": """## 来源与用途（手工维护）

- **数据来源**：`translate_page_leave`，按 userid+session_id 去重取最后一次（见表注释）
- **同步方式**：ETL
- **业务含义**：用户每日页面内容复杂度汇总
- **建议粒度**：用户 × 日
- **主键 / 唯一键**：见字段；使用前核对
- **常用过滤**：`dt`
- **关联建议**：用户 id
- **勿想当然**：去重规则依赖 session；与 translate 次数口径不同
""",
    "user_commercial_intent_day": """## 来源与用途（手工维护）

- **数据来源**：商业意愿相关埋点汇总（付费页曝光 / 限额阻断 / 支付入口等，见表注释）
- **同步方式**：ETL
- **业务含义**：用户每日商业意愿指标
- **建议粒度**：用户 × 日
- **常用过滤**：`dt`
- **关联建议**：用户 id
- **勿想当然**：意愿 ≠ 转化；需与订单表交叉验证
""",
    "user_workflow_action_day": """## 来源与用途（手工维护）

- **数据来源**：工作流相关埋点日汇总（批量翻译 / 高级功能等，见表注释）
- **同步方式**：ETL
- **业务含义**：用户每日工作流嵌套/高级能力使用
- **建议粒度**：用户 × 日
- **常用过滤**：`dt`
- **关联建议**：用户 id
- **勿想当然**：覆盖人群可能偏小，勿当全体活跃定义
""",
    "user_churn_signal_day": """## 来源与用途（手工维护）

- **数据来源**：流失信号日表（ETL）
- **同步方式**：ETL
- **业务含义**：用户每日流失相关信号
- **建议粒度**：用户 × 日
- **常用过滤**：`dt`
- **关联建议**：用户 id；可与 `user_payment_summary` 交叉
- **勿想当然**：信号定义以字段注释/探查为准，禁止按表名臆造
""",
    "user_payment_summary": """## 来源与用途（手工维护）

- **数据来源**：支付/会员结果汇总（ETL）
- **同步方式**：ETL
- **业务含义**：用户支付侧摘要（具体字段见结构段）
- **建议粒度**：用户级摘要
- **关联建议**：与订单清洗表核对口径后再用
- **勿想当然**：行数远小于注册用户，仅为有支付相关行为子集
""",
    "user_tag_metrics_current": """## 来源与用途（手工维护）

- **数据来源**：用户标签/活跃指标当前快照
- **同步方式**：ETL 快照（`ds` 为快照日）
- **业务含义**：近 7 日活跃天数、翻译次数等当前标签
- **建议粒度**：`userid` + `ds`
- **常用过滤**：先确认最新 `ds`
- **关联建议**：`userid` → 用户
- **勿想当然**：不是全历史；用前查 `MAX(ds)`
""",
    "imm_entity_current_profile": """## 来源与用途（手工维护）

- **数据来源**：实体（用户/分析主体）当前画像
- **同步方式**：ETL
- **业务含义**：母语、安装日周、设备数等
- **建议粒度**：`analyze_id` / `userid`（字段均为 VARCHAR，注意类型）
- **常用过滤**：按需
- **关联建议**：与 BIGINT 用户 id 关联需 cast；先抽样对齐
- **勿想当然**：`install_day` 口径是否排除 1970 占位需过滤
""",
    "imm_entity_daily_funnel": """## 来源与用途（手工维护）

- **数据来源**：实体日漏斗（安装→激活→转化等，以字段为准）
- **同步方式**：ETL；行数很大，必须按日过滤
- **业务含义**：漏斗分析宽表
- **建议粒度**：实体 × 日
- **常用过滤**：日期字段（以结构段为准）
- **关联建议**：经 `analyze_id`/`userid` 与画像表对齐
- **勿想当然**：禁止无日期全表扫描
""",
    "imm_entity_daily_feature_usage": """## 来源与用途（手工维护）

- **数据来源**：实体日功能使用
- **同步方式**：ETL
- **业务含义**：功能使用日汇总
- **建议粒度**：实体 × 日 × 功能维（以字段为准）
- **常用过滤**：日期
- **关联建议**：同 entity 体系
- **勿想当然**：功能枚举以实际字段/探查为准
""",
    "imm_token_used": """## 来源与用途（手工维护）

- **数据来源**：Token 消耗汇总/明细（相对较小）
- **同步方式**：ETL 或业务同步
- **业务含义**：模型 token 使用
- **建议粒度**：以字段为准
- **关联建议**：与 `token_used_aw` 区分体量与粒度
- **勿想当然**：不要默认与百亿级 `token_used_aw` 等价
""",
    "token_used_aw": """## 来源与用途（手工维护）

- **数据来源**：Token 使用明细（体量极大，十亿级+）
- **同步方式**：持续/批写
- **业务含义**：细粒度 token 消耗
- **建议粒度**：明细行
- **常用过滤**：**必须**时间/用户强过滤
- **关联建议**：先读字段再关联
- **勿想当然**：禁止无过滤聚合；优先用汇总表若存在
""",
    "exchangerates": """## 来源与用途（手工维护）

- **数据来源**：汇率维表（约数十行）
- **同步方式**：维护型小表
- **业务含义**：多币种金额折算
- **建议粒度**：币种
- **关联建议**：订单 `currency` → 本表
- **勿想当然**：确认汇率日期/基准币种后再用于收入汇总
""",
    "imm_user_type": """## 来源与用途（手工维护）

- **数据来源**：用户类型标注表
- **同步方式**：ETL/规则产出
- **业务含义**：用户类型分类（具体枚举探查后用）
- **建议粒度**：用户级
- **关联建议**：用户 id
- **勿想当然**：与埋点字段 `user_type` 可能同名异义，禁止混用未核对
""",
    "ads_member_valid_daily_snapshot": """## 来源与用途（手工维护）

- **数据来源**：ADS 层会员有效日快照
- **同步方式**：ETL
- **业务含义**：每日有效会员规模类指标（以字段为准）
- **建议粒度**：日快照
- **常用过滤**：快照日
- **关联建议**：会员分析优先 ADS/DWS，原始订单作核对
- **勿想当然**：快照时点与「当日曾有效」口径可能不同
""",
    "imm_view_dau": """## 来源与用途（手工维护）

- **数据来源**：DAU 视图（VIEW）
- **同步方式**：视图定义依赖底层表
- **业务含义**：日活口径封装
- **建议粒度**：按视图字段
- **常用过滤**：使用前 `SHOW CREATE VIEW` / 查字段并核对定义日期范围
- **勿想当然**：视图口径可能随底层变更；重要结论要回底层核对
""",
    "vw_user_native_language": """## 来源与用途（手工维护）

- **数据来源**：用户母语视图
- **业务含义**：母语映射封装
- **关联建议**：用户 id；与 `imm_entity_current_profile.native_language` 可能同源或不同，需核对
- **勿想当然**：先看视图定义再 join
""",
    "vw_device_user_language_map": """## 来源与用途（手工维护）

- **数据来源**：设备-用户-语言映射视图
- **业务含义**：设备与用户语言桥接
- **关联建议**：埋点 `device_id` ↔ 用户
- **勿想当然**：一对多时会放大行数，先去重或选主设备规则
""",
}


def patch(table: str, section: str) -> None:
    path = IMM / f"{table}.md"
    if not path.exists():
        print("MISSING", table)
        return
    text = path.read_text(encoding="utf-8")
    start = text.find("## 来源与用途")
    if start < 0:
        print("NO SECTION", table)
        return
    # end at AUTO schema or next ## after 来源
    auto = text.find("<!-- AUTO:SCHEMA:START -->", start)
    if auto < 0:
        end = len(text)
    else:
        end = auto
    new_text = text[:start] + section.rstrip() + "\n\n" + text[end:]
    path.write_text(new_text, encoding="utf-8")
    print("OK", table)


def main():
    for t, sec in ENRICH.items():
        patch(t, sec)


if __name__ == "__main__":
    main()
