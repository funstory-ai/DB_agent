# 数据与 Databend 踩坑手册（避坑指南）

> **强制**：每次开查前先读本文件；新坑先问用户再写入。范围仅 `immdata`。  
> **异常数据**：必须按 [`anomaly_review.md`](anomaly_review.md) 给出**举例 + 占比**，便于判断。

## 记录模板

```
### Pxxx — 简短标题
- 发现日期：YYYY-MM-DD
- 涉及：库/表/字段
- 现象：
- 举例：
- 占比：异常数 / 分母 = x.xx%
- 根因：
- 正确做法 / 规避：
- 示例 SQL：（可选）
```

---

## 条目

### P002 — `user_behaviour` 体量极大，禁止无过滤全表扫
- 发现日期：2026-08-12
- 涉及：`immdata.user_behaviour`（约百亿行级）
- 现象：无时间/事件条件的查询极慢或失败
- 根因：埋点明细全量堆积
- 正确做法 / 规避：始终加 `created_ts`（或日期）窗口，并尽量过滤 `event_name`；能用日汇总/`dwd_behaviour` 则不用明细

### P003 — `install_day` 可能为 `1970-01-01` 占位
- 发现日期：2026-08-12
- 涉及：`user_behaviour.install_day` 等
- 现象：安装日分布异常、新用户队列被污染
- 根因：缺失安装日被写成 epoch
- 正确做法 / 规避：排除 `install_day <= '1970-01-01'` 或 `install_day IS NULL`；重要口径用业务表 `imt_deviceinfo.installtime`

### P004 — `imt_*` 软删字段 `isdeleted`
- 发现日期：2026-08-12
- 涉及：`imt_userinfo` 等（用户表存在少量 `isdeleted=1`）
- 现象：人数/订单略多于后台
- 根因：未过滤软删
- 正确做法 / 规避：`WHERE COALESCE(isdeleted, 0) = 0`

### P005 — 用户 ID 字段名与类型不统一
- 发现日期：2026-08-12
- 涉及：`id` / `uid` / `userid` / `user_id`；部分为 VARCHAR（如 `user_translate_day.userid`、`imm_entity_current_profile.userid`）
- 现象：join 失败、类型隐式转换、关联错人
- 根因：多表多来源命名不一致
- 正确做法 / 规避：以目标表文档为准；`imt_userinfo.id` 为注册用户主键候选，但 `uid` 需单独核对；跨类型用显式 `CAST`，先抽样对账

### P006 — `user_behaviour` 账号 ID 在 `ex_int_arg1`（登录才有）；主实体仍是设备
- 发现日期：2026-08-12；更正：2026-08-14（业务确认）
- 涉及：`user_behaviour.ex_int_arg1`（= 登录 userid）；主关联键仍是 `device_id`
- 现象：按用户去重需弄清登录态；未登录事件无账号 ID
- 根因：埋点以设备为主；**登录才写 `ex_int_arg1`，未登录为空（正常）**
- 核查（2026-08-14）：
  - `user_type=anonymous` → 填充率 ≈0%；`free/trial/monthly/yearly` 等 → ≈99%+
  - 设备已在 `imt_deviceinfo` 仍可能打出 anonymous 事件（无 userid）——设备表有绑定 ≠ 每条行为都已登录
  - 独占设备上有值时与 deviceinfo.userid 一致率极高
  - **曾误报**「订单人群 beh-uid 仅约 40%」：系分析擅自用「近 30 天 + 仅 translate_page」收窄行为窗（需求未要求活跃），**不是**原表/`ex_int_arg1` 质量问题；同窗全事件匹配约 95%+。该 40% **作废，禁止再当完备性结论**
- 正确做法 / 规避：
  - **并订单/账号行为（P016）**：`deviceinfo` 与 `ex_int_arg1` **必须一起用**，勿单独替代
  - `ex_int_arg1` 仅登录事件有值；anonymous 为空属正常
  - `dwd_behaviour.user_id` 可能同源，引用前核对

### P007 — 订单 `finished` 不等于已付费现金单
- 发现日期：2026-08-12
- 涉及：`imt_subscriptiongoodsorder.orderstatus`；`dwd_order_clean`
- 现象：用 `orderstatus='finished'` 统计收入/付费人数偏大或含试用
- 根因：试用等也会 finished；`amountpaid` 可能为 0
- 正确做法 / 规避：分析优先 `dwd_order_clean` 的 `is_paid_order` / `is_trial_order` 等标志；原始表需结合 `ordertype`、`amountpaid`、`membership`

### P008 — `amount` 与 `amountpaid` 单位可能不一致
- 发现日期：2026-08-12
- 涉及：订单相关表
- 现象：金额差 100 倍或币种混乱
- 根因：`amount` 多为标价小数；`amountpaid` 常见最小货币单位整数；另有多币种
- 正确做法 / 规避：汇总前统一单位与币种；折算用 `exchangerates` 并确认基准

### P009 — `platform_type` 枚举不干净
- 发现日期：2026-08-12
- 涉及：`user_behaviour.platform_type`
- 现象：mobile 统计偏少或重复
- 根因：除 desktop/mobile/tablet/unknown 外，混入 `iPhone*` 机型字符串
- 正确做法 / 规避：统计前归并（如 `platform_type IN ('mobile') OR platform_type ILIKE 'iPhone%'`），或先查枚举再定口径

### P010 — 临时表不当正式口径；任务结束应收拾试错产物
- 发现日期：2026-08-12；补充：2026-08-13
- 涉及：`tmp_*` / `t_*` / `temp*` / `test*` / 带日期后缀的一次表；本地 adhoc / 多版 output
- 现象：误当正式口径；复跑不稳定；任务结束后堆满试错、无法映证以哪版为准
- 根因：探索性产物未清、未留档
- 正确做法 / 规避：
  - 分析**默认不引用**库内临时表；若必须用，在 SQL 头注释来源与失效风险
  - 交付后：定稿进 `docs/tasks/` + `sql/reports/`；本地试错清零（见 `docs/tasks/README.md`）
  - 本仓只读不能 DROP 库表；库内试错表由有写权限方在任务结束后删除

### P011 — 事件名存在拼写变体
- 发现日期：2026-08-12
- 涉及：如 `translage_page_daily`（疑似 translate 拼写错误）
- 现象：按标准事件名过滤漏数
- 根因：埋点历史拼写不一致
- 正确做法 / 规避：重要指标先对 `event_name` 做模糊/枚举探查，再定最终事件列表

### P012 — `dwd_order_clean` / `dws_order_user_firsts` 为历史过程表，不可信，默认无视
- 发现日期：2026-08-12（业务确认）
- 涉及：`immdata.dwd_order_clean`、`immdata.dws_order_user_firsts`
- 现象：数据停在旧任务时点（如 order_day 最大约 2026-03-31），不能支撑近窗分析
- 根因：过往任务中间过程表，非持续维护的正式口径
- 正确做法 / 规避：**默认不使用**；订单/试用/付费一律以 `imt_subscriptiongoodsorder` + `amountpaid` 口径（P013）为准

### P013 — 试用/付费以 `amountpaid` 为准；`onetime*` 兑换码不算试用
- 发现日期：2026-08-12（纠错）；补充：2026-08-13
- 涉及：`imt_subscriptiongoodsorder`
- 正确做法 / 规避：
  - **付费**：`orderstatus='finished' AND COALESCE(amountpaid,0)>0`
  - **试用候选**：`finished AND COALESCE(amountpaid,0)=0`
  - **排除淘宝等一次性兑换码**：`subscriptiongoodssnap` 中 `SubscriptionType` 以 `onetime` 开头（如 `onetime_3day` / `onetime_7day` / `onetime_yearly`），常见 `ordertype='code'` 且 `amountpaid` 为 0/NULL
  - 识别示例：`CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'`
  - 不要只用 `ordertype LIKE '%trial%'`

### P014 — 极高翻译次数常与「单设备多账户」重合（已核查）
- 发现日期：2026-08-12；核查：2026-08-12
- 涉及：试用未付费队列 × `user_behaviour.translate_page`
- 现象：多名用户出现同量级超高次数；均值易被拉高
- **举例**：设备 `LK8j8qPLDa3gUgujz9Yt7RtmltkXP0bD` ≈ **242,990** 次 `translate_page`，队列内挂 **9** 个 userid（如 `310455` … `6966781`）
- **占比**（近90天试用未付费且有设备）：
  - 有翻译用户中 ≥10 万次：**10 / 32,968 ≈ 0.030%**
  - 其中 **9/10** 落在共享设备；这 10 人贡献用户侧累加次数 **≈14.8%**（2.43M/16.49M）
  - 至少一台设备与其他未付费试用用户共享：**12,652 / 34,769 ≈ 36.4%**（共享≠都是羊毛党）
- 根因：B1 多设备累加 + 共享设备全量计入每账户；头部多为羊毛党形态（P018-C）
- 正确做法 / 规避：转化只用订单 userid；行为报表分桶并标注头部/共享设备。详见 `docs/anomaly_review.md` 案例 B

### P015 — `imt_deviceinfo` 曾存在不应有的 `(userid, deviceid)` 重复（已清理）
- 发现日期：2026-08-12；核查清理：2026-08-12
- 涉及：`imt_deviceinfo`
- 历史现象：同一用户同一设备多行（非软删）；例 `userid=916079` 同 device 10 行
- 历史占比：重复键对约 **0.060%**（4357/7229267）
- **清理后复核**：`pairs=rows=7,229,267`，`dup_pairs=0`，`extra_rows=0`（已通过）
- 正确做法 / 规避：业务侧已按 `MAX(id)` 去重清理；分析侧仍可用 `DISTINCT` 作防御性写法。详见 `docs/anomaly_review.md` 案例 A

### P016 — 订单/账号并行为：`deviceinfo` + `ex_int_arg1` 双路径（勿只用其一）
- 发现日期：2026-08-12；修订：2026-08-14（业务确认）
- 涉及：`imt_deviceinfo.deviceid` = `user_behaviour.device_id`；`user_behaviour.ex_int_arg1` = 登录 userid（P006）
- 现象：设备表有漏；仅用 `ex_int_arg1` 又只覆盖登录事件，单独用任一路径都会少人
- 完备性（任务二相关）：
  - **【作废指标】** 曾报试用未付费 beh-uid ≈42%：分析侧**擅自**加「近 30 天」行为窗 + 仅 `translate_page`，需求是近 90 天试用未付费、**未要求活跃过滤**；却归因原表，属误导。同窗全事件复现 ≈95%+。
  - 双路径仍保留：deviceinfo 与登录态 `ex_int_arg1` 互补（设备缺口 / anonymous 事件），**禁止**再用错误的 40% 证明「只能靠设备表」。
  - 流失：无 deviceinfo 约 9.4%，其中部分可用 `ex_int_arg1` 补回
  - 试用未付费：无 deviceinfo 约 29.5%，其中 **64.4%** 可补回（全人群 +19.0pp → 覆盖约 89.5%）
- 正确做法 / 规避：
  - **标准并表（强制）**：账号行为 =  
    ① `userid → imt_deviceinfo → behaviour.device_id`  
    **并上**  
    ② `userid = behaviour.ex_int_arg1`（限时、建议再滤事件）  
    两路结果按业务去重/累加（次数类通常 `UNION` 设备事件后再按 userid 汇总，避免双计需按事件主键或先收窄）
  - **禁止**只走 deviceinfo 或只走 `ex_int_arg1`
  - 转化率仍只走订单 userid（P018）；本条管的是**行为取数覆盖**

### P017 — `user_behaviour`：必须限时，且禁止对 `created_ts` 套函数
- 发现日期：2026-08-12（业务确认）
- 涉及：`immdata.user_behaviour.created_ts`
- 现象：直接大范围查/并表极慢；`DATE(created_ts)` 等写法会进一步拖垮
- 根因：宽表体量大；对时间列套函数妨碍剪枝
- 正确做法 / 规避：
  - 每次查询：`created_ts >= ... AND created_ts < ...`（常量边界）
  - 需要按日：拆成日区间比较，不要 `DATE(created_ts) = '...'`
  - 并表前先收窄 `device_id` / `event_name`

### P018 — 单账户多设备 / 单设备多账户：转化与行为口径（已确认）
- 发现日期：2026-08-12（业务确认）；**补充 2026-09-20**：转化主体「有账号用账号，无账号用 device_id」
- 涉及：转化类指标；`imt_deviceinfo` ↔ `user_behaviour`
- 正确做法 / 规避：
  - **A 转化率**：多设备归并到 **userid** 计算，避免按设备虚高转化
  - **B 行为次数**：用户下多设备事件 **累加**（描述性指标）
  - **C 单设备多账户**：一般是羊毛党、量不大；**付费分子走订单 userid**，behaviour 只做描述、**不进入付费分子**
  - **D 转化主体（强制）**：凡转化 / 漏斗 / 转化率，先归到「人」再算：
    - **有账号**（订单 `userid`，或行为 `ex_int_arg1` / `deviceinfo.userid`）→ 主体 = **userid**；同一账号多设备只算 1 人
    - **没有账号** → 主体 = **device_id**；不要把未注册设备滤掉，也不要当成空 userid 丢掉
    - 禁止按设备把已有账号的人拆成多次转化
    - 付费分子仍只能是订单 userid（无账号无法成单）；分母按上面的人粒度

### P019 — 抽样复核：目的是验 SQL，禁止为抽样重跑全量；指标随任务变
- 发现日期：2026-08-13（任务一抽样实践）
- 涉及：交付前抽样；`docs/sample_validation.md`
- 现象：任务一为抽 N=20，先对 3 万+ cohort 重算全量翻译次数再建分层池，单次耗时十余分钟；叠加防 OOM 的「每设备拆 5 次 COUNT」后更慢。若照此模式，后续任务可能「光抽样抽一小时+」。
- 根因：
  1. 把「分层标签」算在全量结果上，等价再跑一遍主报表
  2. 误把「翻译五类次数」写成通用硬性标准（转化率等任务并不适用）
- 正确做法 / 规避：
  - **目的**：抽几个样本，用**另一条更窄的路径**核对主 SQL 有没有算错；不是再产一份全量数
  - **核对字段随任务定**：次数任务对次数；转化率对「是否分母/分子归属正确」；漏斗对关键节点。禁止默认永远验翻译次数
  - **性能红线**：抽样不得重跑与主交付同级的全表/全 cohort 聚合。优先：从已交付 Excel/结果集抽行；或先抽轻量 userid 集合再只对样本独立重算
  - **N**：默认约 20（或用户指定）；几分钟～十余分钟量级可接受；若预估接近「再跑一遍大任务」必须改方案
  - **汇报**：只对话告知通过/不通过与异常样例；**不为抽样单独建表或另存结果文件**
  - 任务一脚本 `sample_validate_task1.py` **仅适用于任务一口径**，不可套用到转化率等其它任务

### P021 — 非正式小询问禁止「半小时起步」：先抽样/短窗，禁止对 behaviour 串行大扫
- 发现日期：2026-08-14（业务反馈）
- 涉及：对话中的口径核对、占比、完备性等小问题；`user_behaviour`
- 现象：一个「补洞能补多少」「空值占比」类问题动辄 30–60+ 分钟；中途 OOM 再重跑更慢
- 根因（实践）：
  1. 把小问题做成**全 cohort × 90 天 behaviour** 精确重算
  2. **几十轮串行** `ex_int_arg1 IN (250人)` 扫宽表（一轮数分钟 × 50+）
  3. 失败后换更大窗口/更大集合，而不是先收敛口径
- 正确做法 / 规避（**非正式询问默认**）：
  1. **先判题型**：要精确全量数，还是方向/占比？未说清则先给**抽样估计**（N=500～2000），并标明「抽样」
  2. **优先复用**已有 `output/*.xlsx` 的 userid / 是否有 deviceinfo，禁止为小问题重算任务一/二全量
  3. **时间窗**：探测类默认 **1～7 天**；只有用户明确要近 90 天全量才拉长
  4. **事件**：先 `event_name` 收窄（如仅 `translate_page`），禁止无事件滤的行为全扫
  5. **集合**：先收窄到「无 deviceinfo」等小集合再碰 behaviour；`IN` 列表控制在可控大小，或 **一次 SQL** 用 `EXISTS`/半连接，禁止 50+ 轮串行
  6. **耗时红线**：非正式问题目标 **数分钟内**出结论；预估会超过 ~10 分钟必须改方案或先问是否接受抽样
  7. OOM 后：缩小窗/抽样/改半连接，**不要**原样加重试
  8. **反例（task6）**：对 ~8k 试用 userid **分批 `ex_int_arg1 IN (2000)` 扫 behaviour**，单批可十余秒、合计可到十余分钟；同窗一次 `订单 LEFT JOIN behaviour`（常量时间界）可约半分钟出 90%+ 匹配率。优先一次半连接，忌串行 IN。

### P025 — 细节易分歧时必须先问用户，禁止擅自加口径
- 发现日期：2026-08-14（业务纠正）
- 涉及：一切查数/匹配/完备性；尤其 `user_behaviour` 时间窗、事件过滤、「活跃」等
- 现象：需求为「近 90 天试用未付费」与行为匹配时，分析擅自把行为窗收成近 30 天 + 仅 `translate_page`，算出 ≈40% 匹配，并误导为原表/`ex_int_arg1` 质量差；业务同窗全事件验证 ≈95%+
- 根因：把未声明的「活跃/性能收窄」写成完备性结论；低匹配先甩锅原表
- 正确做法 / 规避：
  1. **时间窗、事件范围、是否活跃、去重主体、是否含兑换码**等易分歧点：需求未写清 → **先问再查**
  2. 性能收窄（短窗、单事件、抽样）可以做，但必须标明「估计/非正式」，**禁止**当成正式完备性或字段质量结论
  3. 低匹配/异常：先核对自身 SQL 是否对齐需求，再怀疑原表
  4. 该 40%/42% 指标 **作废**

### P026 — behaviour 匹配禁止串行大 `IN`；优先一次半连接
- 发现日期：2026-08-14
- 涉及：`user_behaviour` 与订单/人群匹配；task6 `_tmp_trial_beh_match.py`
- 现象：分批 `ex_int_arg1 IN (2000)` 扫表，合计可达十余分钟；同窗 `订单 LEFT JOIN behaviour` 约半分钟且匹配 90%+
- 根因：多轮重复扫宽表；另有 `CAST(join键)`、`CROSS JOIN` 动态 bounds 破坏剪枝
- 正确做法 / 规避：常量时间界 + **一条**半连接/`EXISTS`；先投影去重 ID 再 join；忌串行大 IN（呼应 P021）

### P024 — 会员有效覆盖须含兑换码（onetime* **与** `ordertype=code`）
- 发现日期：2026-08-14（211939）；补充同日（90644）
- 涉及：流失/续费判断；`imt_subscriptiongoodsorder`
- 现象：
  1. 仅用 `amountpaid>0`：淘宝 `onetime_yearly`（amountpaid NULL）漏计 → 误判流失（211939）
  2. 只认 snap `onetime*`：部分 `ordertype='code'` 但 `SubscriptionType` 仍是 `monthly`/`yearly`（amountpaid NULL）仍漏计 → 误判流失（90644）
- 根因：兑换码路径多样；snap 类型不一定以 `onetime` 开头
- 正确做法 / 规避：
  - **会员覆盖订单** = `finished` 且 `subscriptionday>0` 且（`amountpaid>0` **或** snap 含 `"SubscriptionType":"onetime` **或** `LOWER(ordertype)='code'`）
  - 真试用（amountpaid=0 且非 onetime、非 code）**不进**覆盖
  - 流失：`MAX(cover_end)` 落在观察窗且 `<NOW()`；刚续费/兑换码续期后出队
  - 「试用未付费」历史排除与覆盖同一集合（含 code）
  - 与 P013 分工：P013 管试用**候选单**排除 onetime；P024 管**有效期/流失/是否曾获会员**

### P023 — Databend 保留字不可作列名（如 `share`）
- 发现日期：2026-08-14
- 涉及：DDL / 别名；例：`imm_workspace_daily_dim`
- 现象：`CREATE TABLE ... share DOUBLE` → error 1005，`share` unexpected / reserved keyword
- 根因：`share` 等为方言保留字
- 正确做法 / 规避：列名改用 `share_ratio` 等非保留标识；必要时用反引号/引号引用（优先改名）；建看板 DDL 写完应用写仓试跑 CREATE

### P022 — 按天累计看板：事件少≠直查快；须实测后决定中间表
- 发现日期：2026-08-14（实测 + 业务确认）
- 涉及：挂 Superset / 按日刷新的累计看板；源多为 `user_behaviour`
- 现象：目标事件行数仅百级，但 90 天「按日 UV/PV + 多 COUNT DISTINCT」仍可达 **~45–53s**，不适合看板交互
- 根因：宽表按时间窗扫描成本与「命中行数」不成正比；多 DISTINCT / 多事件仍重
- 正确做法 / 规避：
  1. **选型必须实测**：先跑目标看板 SQL（7d/30d/90d）记耗时；勿仅凭事件量猜「能单 SQL」
  2. **阈值经验**：交互看板单图经常 **>约 10s**（尤其 30d+）→ **建日汇总中间表 + 日更 TASK**；昨日增量窗通常可压到 ~1s 级
  3. **中间表模式**（对齐 `imm_user_target_lan_stats`）：
     - 粒度按日（北京自然日 `dt_bj`）或业务主键
     - 全量回填一次；TASK 只扫「昨天 00:00～今天 00:00（北京）」→ UTC 边界：`add_hours(add_days(date(add_hours(now(),8)),-1),-8)` ～ `add_hours(date(add_hours(now(),8)),-8)`
     - 优先 `REPLACE INTO ... ON (...)`；**慎用**「先 DELETE 近 N 日再 INSERT」——INSERT 失败会掏空近窗（见 P027）；多语句 TASK 须 `BEGIN…END`（见 **P028**）
     - 本仓只读，DDL/TASK 由写仓执行，SQL 落 `sql/reports/*_etl.sql`
     - 日更后查 `MAX(业务日)` 是否对齐昨日；落后则 refill，勿只抽日 SUM
  4. **看板只读中间表**；探查/一次性仍可短窗直查 behaviour（P021）
  5. **样例**：Google Workspace → `imm_workspace_daily_*`（task5）；付费墙 → `imm_paywall_daily_*`（task6，勿用 `ads_ab_paywall_*`）
  6. 日 UV 之和 ≠ 窗口去重 UV；累计 PV 可用 `SUM() OVER (ORDER BY dt)`；严格累计 UV 需设备集合/bitmap 另表

### P020 — 母语/语言拆分：用 `imm_device_native_language`（设备级）；账号级按 cnt 合计取最大语
- 发现日期：2026-08-13（业务提供 ETL；账号归并同日确认）
- 涉及：`imm_device_native_language`；上游 `imm_user_target_lan_stats`；可选 `imm_device_native_language_without_fb`
- 现象：按语言拆分时误从埋点现场猜母语，或把设备母语直接当账号母语导致一人多语/重复计数
- 根因：正式母语标签由日批任务推断，且粒度为 **device_id**
- 正确做法 / 规避：
  - 区分语言的 SQL：**默认 join `imm_device_native_language`**（`device_id`）；推断 = `target_language` Top1（累计 translate_page）优先，否则昨日 `interface_language` Top1
  - 上游累计表：`imm_user_target_lan_stats`（键是 device×target_language，表名含 user 勿误解）
  - **账号级母语（已确认）**：同一 `userid` 下，按 `native_language` 把各设备的 `cnt` **合计**，取合计数最大的语言作为该 userid 的母语
  - `without_fb`：无 interface 兜底，仅明确要求时用；默认用主表
  - 详表文档：`docs/tables/immdata/imm_device_native_language.md`

```sql
-- 账号级母语（P020）
WITH per_lang AS (
  SELECT
    userid,
    native_language,
    SUM(cnt) AS cnt_sum
  FROM immdata.imm_device_native_language
  WHERE userid IS NOT NULL AND userid <> ''
    AND native_language IS NOT NULL AND native_language <> ''
  GROUP BY userid, native_language
),
ranked AS (
  SELECT
    userid,
    native_language,
    cnt_sum,
    ROW_NUMBER() OVER (
      PARTITION BY userid
      ORDER BY cnt_sum DESC, native_language
    ) AS rn
  FROM per_lang
)
SELECT userid, native_language, cnt_sum
FROM ranked
WHERE rn = 1;
```

### P027 — 中间表日更 / 回填：叠层与近窗空洞
- 发现日期：2026-08-20（看板中间表复盘抽象）；**补充 2026-08-27**（task6 付费墙 wide_hit 实案）
- 涉及：按日中间表 + 写仓补丁 / 日更 TASK（任意 `imm_*_daily_*` 类）
- 现象：
  1. 同一 grain 多行，Filter 全空时 `SUM` ≈ kpi×N（task6：7/27+ ratio≈2.002）
  2. 表突然停在旧 `MAX(dt_bj)`，kpi 仍在更新，看板日期落后（task6：卡 7/20）
- 根因：
  1. 全量/回填只跑 INSERT、或 DELETE+INSERT 二次执行 DELETE 失败 → 静默叠层
  2. 日更「先 DELETE 近 N 日再 INSERT」，**INSERT 未进 TASK**（见 **P028**）或空写 → 近窗被掏空
- 正确做法 / 规避：
  - 全量回填：`DROP`+`CREATE`+`INSERT` 或 `TRUNCATE`+`INSERT`（幂等）；禁止只给半截 SQL
  - 日更优先 `REPLACE INTO … ON (主键)`；见 P022
  - 给写仓 SQL 前先查：行数、grain 是否重复、`update_time` 批次数、`MAX(业务日)`、TASK 状态
  - **验收必做**：`COUNT(*)` vs `COUNT(DISTINCT grain)`；`SUM` vs kpi 的 **ratio**（勿只看 diff 绝对值）
  - 用户称已跑完后须再复检，再决定下一份 fix；验收 SELECT 须含**日期新鲜度**，不只抽日 SUM
  - 流程骨架见 `docs/norms/dashboard.md`「写仓前查现状 / 防掏空 / 宽表 SUM 验收」

### P028 — Databend CREATE TASK：多语句须 `AS BEGIN … END;`
- 发现日期：2026-08-27
- 涉及：写仓 `CREATE TASK`；例 task6 `update_imm_paywall_daily_wide_hit`
- 现象：`SHOW TASKS` 显示 Started、last_success 正常，但中间表 `MAX(dt_bj)` 卡住；definition **只有 DELETE、无 INSERT**
- 举例：8/19 部署 wide_hit TASK 后，每晚删近 31 日、从不重插 → max 永停 7/20；refill 回填后 7/27+ SUM≈kpi×2（叠层）
- 根因：裸写 `AS DELETE …; INSERT …;` 时，部分客户端/引擎**只保留第一条**；与 Snowflake 不同，须显式脚本块
- 正确做法 / 规避：
  - 多语句 TASK：**必须** `AS BEGIN DELETE …; INSERT …; END;`（[Databend 文档](https://docs.databend.com/sql/sql-commands/ddl/task/ddl-create_task)）
  - 单语句优先 `REPLACE INTO … ON (…)`，避免 DELETE+INSERT 双语句
  - 写仓跑完 **必查** `SHOW TASKS LIKE '…'` 的 definition 是否含 INSERT，勿只看 state/last_success
  - 定稿 ETL、一次性 fix 脚本中的 CREATE TASK 段须同写法；交付前本仓只读核对生产 definition

### P029 — Superset 挂板 SQL：禁止写死日期上界（「修完反而不更新」）
- 发现日期：2026-08-27
- 涉及：Virtual Dataset / board.sql「包装版」；例 task4 图1b
- 现象：源表 `max(tenantdate)` 已到 8/26，看板 Chart **永远停在 8/24**
- 举例：8/25 修 Input/Output 口径时粘贴 `usage_date < to_date('2026-08-25')` → 上界不含 8/25，最后可见日 8/24
- 根因：调试/对账用固定窗被原样贴进 Superset，且未改回滚动窗
- 正确做法 / 规避：
  - **生产 Dataset 只用滚动窗**：`>= DATEADD(day, -90, NOW()) AND < NOW()`（或北京日等价写法）
  - board.sql 每段标注 **`【可挂 Superset】`** / **`【仅探查·勿挂板】`**；包装版默认后者或内层无日期、外层滚动
  - 修口径后任务文档写清：**Superset Edit SQL → Save → Refresh**（改仓库 SQL ≠ 看板自动更新）
  - 停更排查顺序：先 `MAX(源表业务日)` vs Chart 最后日 → 再查中间表/TASK（勿默认写仓停了）

### P030 — 源表多粒度行混 SUM（非 INSERT 叠层，也会「翻倍」）
- 发现日期：2026-08-25（task4）；与 P027 区分
- 涉及：`imt_teamusagedaily` 等「同键多行不同口径」表
- 现象：看板 `SUM(usage)` 约为正确 token 的 **×2**（广东英辉 8/24：786M vs Input+Output 393M）
- 根因：同一租户×日既有模型**汇总行**（如 `Gemini`）又有 **`GeminiInput`/`GeminiOutput`**，禁止一起 SUM
- 正确做法 / 规避：
  - token 口径：**只** `modelname LIKE '%Input' OR '%Output'`（或只 SUM 无后缀汇总行，二选一）
  - 写 SQL 前读表文档 `docs/tables/immdata/<表>.md` 的「勿想当然」
  - 验收：抽 1 租户 1 日，对比「全 SUM / Input+Output / 仅汇总行」三列，ratio 应≈1 而非 2
  - 与 P027 叠层区分：P027 是**同一 grain 重复行**；P030 是**不同语义行被误加总**

### P031 — 实验/漏斗分母：禁止用 `deviceinfo` INNER JOIN 把未注册踢出（注册墙类 AB 会失真）
- 发现日期：2026-08-28（`query_paywall_ab_20260821` v1→v2）
- 涉及：`imt_deviceinfo` × `user_behaviour`；付费墙 A/B（有无注册墙）等「处理变量影响注册」的实验
- **上位规则**：本件是 **P032**（需求潜在口径审查）的实案；表文档已写「仅注册有 deviceinfo」，仍因未对照需求推一步而写错
- 现象：
  - v1：`deviceinfo` **INNER JOIN** 埋点取 `ab_tag` → 分母≈**已注册**新装；A/B/C/D **注册后** 3 日付费都 ~0.8%，误判「去注册墙无影响」
  - 实际完整漏斗：A 注册率 **25.0%** vs B **21.3%**；3 日付费 / 新装 device 为 **0.17% vs 0.14%**（A 略高）；注册后付费仍 ~0.66% 无差
- 举例（8/21～8/28，≥1.32.6，`install_day` 新装 device）：
  - 埋点新装：A 43,105 / B 34,647；能进 `deviceinfo`：A 10,778（25%）/ B 7,374（21%）
  - v1 内连接分母只剩 ~1/4～1/5 设备，且 **A 进表率高于 B**（注册墙本身推注册）
- 根因（SQL 误差链）：
  1. `imt_deviceinfo` **基本只有注册设备**；未注册可有埋点、无业务设备行
  2. 实验处理是「有无注册墙」→ **直接改变谁进得了分母**
  3. 对 `deviceinfo` 做 **INNER JOIN** = 先按「已注册」筛选再算 checkout/试用/付费 → 把实验最该看的注册段砍掉，A vs B 对比失真
  4. 付费/checkout 分子本就依赖 userid，分母若也只用注册人群，只能回答「注册后转化」，不能回答「新装全体漏斗」
- 正确做法 / 规避：
  - **分母（主）**：设备级埋点新装 **device**（**默认 P034**：`init_page_daily` + `is_new_user_today='1'` + 实验所需的 `ab_tag`/版本等）；`deviceinfo` 只 **LEFT JOIN** 补 userid
  - ❌ 勿再把「首条 `translate_page`」当成新装分母（那是激活/翻译进组；见 P034）
  - **主率**：注册率、checkout/试用/付费 / **新装 device**（完整漏斗，未注册计 0）
  - **辅率**（可选）：同指标 / linked userid（注册后转化；≈旧口径，须标明）
  - 写 AB/漏斗 SQL 前自问：处理变量是否影响注册/进 `deviceinfo`？若是 → **禁止**用内连接注册表当唯一分母
  - 抽样：必须抽到「未注册仍在分母」的 device；否则分母口径未验过
- 关联任务：`docs/tasks/query_paywall_ab_20260821.md`；定稿 SQL v2：`sql/reports/query_paywall_ab_20260821.sql`

### P032 — 开查前必须对照需求做「潜在口径」审查（不限于已知表坑）
- 发现日期：2026-08-28（由 P031 升级：用户要求泛化）
- 涉及：所有 `query` / 对比实验 / 漏斗 / 转化率；不限于 deviceinfo
- 现象：表文档/pitfalls **已有事实**（如「deviceinfo 仅注册」），SQL 仍选错分母/分子/时间锚点 → 数字能跑通、结论答错题
- 根因：把「会用表、会写 join」当成口径正确；**没有把需求里的处理变量 / 对比意图，推演到「会不会改写谁进分母、谁进分子」**
- 正确做法 / 规避（写正式 SQL **之前**强制过一遍，口头或写进任务文档均可）：
  1. **需求真正要回答什么**：完整漏斗 vs 条件转化？组间因果 vs 描述性占比？
  2. **处理变量 / 分组条件**是否会改变：注册、登录、进某表、出某事件、时间窗能否跑满？
  3. **分母候选**各自对应哪一问：埋点 device / 注册 userid / 触墙人群 / 下单人群——选错 = 答错题
  4. **分子与分母是否同源、同窗**：禁止「分子用 A 表安装锚点、分母用 B 表活跃」却不声明
  5. **已知表约束 × 本题**：读到「仅注册有数据」时，必须再问一句——本题是否在比注册本身？若是 → 该表不能当内连接唯一分母
  6. 说不清或两套口径都可能对 → **先问用户（叠 P025）**，禁止自定一版当正式结论
- 反例类型（下次同类要先拦）：
  - 注册墙/登录墙 AB → 内连注册表当分母（P031）
  - 「新装转化」→ 分母用行为活跃 / `install_day` 脏字段，分子用 `installtime`
  - 「去某墙效果」→ 分母先滤「已触墙」再比转化（条件化掉处理）
  - 未跑满观察窗的 cohort 与已跑满的混报同一 N 日率
- 与 P025 关系：P025 是「细节没写清要先问」；P032 是「写清了也要推演潜在偏倚」——两道都要过

### P033 — 账号级「新装用户」转化：必须过滤老号（勿裸用 min(installtime)）
- 发现日期：2026-08-31（用户确认写入）
- 涉及：账号级新装转化 / 付费新用户功能使用率等；`imt_deviceinfo.installtime`、`imt_userinfo.createtime`、`imt_subscriptiongoodsorder`
- 现象：`userid = min(installtime)` 会被当成「新装」，但 `installtime` 常≈**迟补上报/入库时间**（设备表历史上报缺口 + 缓存到期再登录），老付费号/老账号会混进新装分母与转化分子
- 根因：
  1. 设备表 `installtime` ≠ 可靠真·首次安装日（见 T021/T023）
  2. iOS 付费单（含首单）`ordertype` 多为 `iospay_renew`，**不能**当老客续费过滤条件（T022）
- 正确做法 / 规避（**账号级、仍用新装锚点**；**不必**扫 `user_behaviour`）：
  - 锚点：`install_anchor = min(installtime)`（活设备、排除 1970）
  - 同时满足才进「干净新装」分母：
    1. **无** `finished` 且 `amountpaid>0` 且 `createtime < install_anchor − 5分钟` 的订单（落库几分钟可保留）
    2. **无** 现金单早于 `userinfo.createtime − 5分钟`（挂账/userid 复用）
    3. `date_diff(day, userinfo.createtime, install_anchor) < 30`（挡老号迟补上报扮新装）
  - 转化分子（N 日首单付费）：lifetime 首笔现金 ∈ `[install_anchor − 5min, install_anchor + N)`
  - **禁止**：裸用 min(installtime) 当分母；用 `iospay_renew` 剔人；默认改成「新注册」口径（除非需求明确）
- 验证（2026-08）：安装前现金 gap≥30 天 29 人 **全剔**；≤5 分钟多数保留；干净分母 3 日首单 CVR ≈ **0.476%**
- 复用 SQL：`sql/reports/query_new_install_user_filter_20260831.sql`
- 关联任务：T021、T022、T023、T024

### P034 — 设备级「新装 / 激活 / 激活率」标准口径（看板与 query 共用）
- 发现日期：2026-09-02（T028）；**2026-09-07 明确：query/AB 新装分母默认同此条（T018）**
- 涉及：`user_behaviour`；日汇总 `imm_app_new_event_device_count_by_utf8_day`（`new_device_count` / `device_count`）
- **标准口径（与「Safari新装激活日活」等 Chart 一致；未另说明的设备级新装分母一律按此）**：
  - **新装**：`event_name='init_page_daily' AND is_new_user_today='1'` → `COUNT(DISTINCT device_id)`（汇总表取 `new_device_count`）
  - **激活（同日）**：`event_name='translate_page' AND is_new_user_today='1'` → 同上
  - **日活**：`event_name='translate_page'` → 按日 `COUNT(DISTINCT device_id)`（汇总表取 `device_count`）
  - **激活率**：**同日** `激活 / 新装`（禁止 AVG 日率跨窗；见 dashboard 比率规则）
  - **时间**：北京自然日；`created_ts` 用常量边界，WHERE 禁止 `DATE(created_ts)`（P017）
- **与「翻译进组」区分**：
  - ❌ 用首条 `translate_page` + `install_day` 当新装分母（T018 旧法）——晚到首译会改写已闭合安装周人数
  - ✅ AB/漏斗要分组时：在 **init 新装 cohort** 上取同事件（或同设备）的 `ab_tag`；**留存/用量**可另用 `translate_page`（如周留存）
- **常见筛选**：`browser_name='Safari'`（Chart 标题「Safari…」通常指浏览器维，**不等于** `install_from='safari'` 渠道）
- **勿混用**：
  - ❌ 安装后 3 日内任意翻译事件当「激活」——那是 cohort 留存/转化口径，不是本看板同日激活
  - ❌ `install_from='official_userscript' AND browser_name='Safari'` 与真 Safari 扩展渠道（`install_from='safari'`）——后者 7/28 后仍 ~80% 激活率（T028）
- **集成流量剔除（T028 Rule A）**：`official_userscript` 且（`ios×Safari` **或** `macos×Maxthon`）的设备/日；**保留** `ImtiOS_*` 等 App UA。勿一刀切全踢 `official_userscript`（jump 前约 2.5k 新装/日、激活 ~70%）
- **手工活跃/月留**（T029）：近 30 天活跃、自然月活、新装月留存若直扫 `user_behaviour`，须加同一 Rule A；定稿 `sql/reports/query_translate_page_monthly_retention_ruleA.sql`
- 复用 SQL：`sql/reports/anomaly_t028_safari_new_install_activation.sql`；写仓：`sql/reports/dashboard_t028_ruleA_embed_kick_etl.sql`；board 样板字段见 `task8_mobile_os_name_board.sql`（`new_user` / `translated_new_user`）
- 挂接：`docs/norms/query.md` 红线、`docs/norms/dashboard.md` §3.1；关联任务 T028、T029、T018

### P035 — Databend `CREATE TASK` CRON 必须是 **6 段**（含秒）
- 发现日期：2026-09-02（T025 写仓）
- 涉及：`SCHEDULE = USING CRON '…' '时区'`
- 现象：`invalid cron expression 0 6 * * 1`（error 1065）
- 根因：套用 Linux/标准 **5 段** cron（`分 时 日 月 周`）；Databend 与本仓已跑通 TASK 均为 **6 段：`秒 分 时 日 月 周`**
- 正确做法 / 规避：
  - 每周一 06:00 上海 → `'0 0 6 * * 1'` + `'Asia/Shanghai'`（**不是** `'0 6 * * 1'`）
  - 每日 UTC 例：`'0 30 21 * * *'`（对照 `task5` / `task6` / T028）
  - 写仓前对照生产 `SHOW TASKS` 的 `schedule` 抄格式；勿从 crontab.guru 等 5 段工具直接粘贴
  - 与 **P028**（多语句须 `BEGIN…END`）并列验收：cron 能建 ≠ definition 含 INSERT

### P036 — Databend `REPLACE … ON (n 列)` 的 `GROUP BY` 列数须对齐
- 发现日期：2026-09-02（T025 周表扩事件回填）
- 涉及：`REPLACE INTO … ON (week_start_day, event_name, device_id) SELECT … GROUP BY …`
- 现象：`assertion left == right failed / left: 2 right: 3`（error 1104），脚本跑到一半中断
- 根因：`ON` 为 **3** 列冲突键，但 `GROUP BY 1, 3` 只有 **2** 列（常量 `event_name` 未进 GROUP BY）；引擎内部按键宽对齐时 assert
- 正确做法 / 规避：
  - `GROUP BY` 显式含齐 ON 键：`GROUP BY 1, 2, 3` 或 `GROUP BY week_start_day, event_name, device_id`（常量列也要写上）
  - 对照生产周 TASK 原文的三列 GROUP BY，勿省「常量事件名」
  - 中断后续跑：REPLACE 幂等，从失败段起即可；确认周 TASK 若已 SUSPEND/DROP，须跑完重建+RESUME
- 关联：`sql/reports/dashboard_t025_week_event_expand_etl.sql`

### P037 — 移动端 `device_id` 已基本脱离 `imt_deviceinfo`（涉及移动端必须说明）
- 发现日期：2026-09-20（业务确认；短窗复核）
- 涉及：`user_behaviour.device_id`（`os_name` 为 android / ios / ipados，及 App UA：`ImtiOS_*` / `ImtFxAndroid_*` / `ImtFxiOS`）↔ `imt_deviceinfo.deviceid`
- 现象：用设备表 INNER JOIN 行为，会系统性漏掉大部分移动端设备；桌面端没有同量级缺口
- 举例 / 占比（非正式短窗，**一天** `init_page_daily`，`created_ts ∈ [2026-09-19, 2026-09-20)`，标明非全量）：

  | 切片 | 设备数 | 能对上 deviceinfo | 命中率 |
  |------|--------|-------------------|--------|
  | 移动端（android/ios/ipados） | 531,718 | 70,004 | **13.2%** |
  | 其中 Android | 428,443 | 46,360 | 10.8% |
  | 其中 iOS | 104,015 | 23,695 | 22.8% |
  | 桌面（windows/macos/linux 等） | 2,600,039 | 1,258,648 | **48.4%** |
  | 移动端存量（非当日新装） | 505,692 | 69,517 | 13.8% |
  | 移动端当日新装 | 26,026 | 487 | 1.9% |
  | 桌面当日新装（对照） | 65,528 | 3,541 | 5.4% |
  | 最大头：Android × UC Browser | 281,551 | 7,054 | **2.5%** |

- 根因：设备表主要覆盖已注册、且历史上写得进业务库的设备（见 P031）。移动端（尤其 Android UC、不少 App）的埋点 `device_id` 已不再落进 `imt_deviceinfo`。当日新装两边都很低，是因为未注册本来就不进设备表，**不能单用新装证明脱离**；存量 13.8% vs 桌面 49.5% 才是差距。
- 正确做法 / 规避：
  - 人群或结果**含移动端**时，交付里必须**提醒并解释**：`imt_deviceinfo` 对不上大部分移动端 `device_id`（上表量级）；禁止把设备表当成移动端设备全集
  - 移动端行为身份以埋点 `device_id` 为准；登录账号仍走 `ex_int_arg1`（P006）。**不要**只用 P016 的 deviceinfo 路径覆盖移动端
  - 桌面端 deviceinfo 路径仍可用，但与移动端混在一个漏斗里时要分开说覆盖率
  - 与 **P018-D** 一起用：有账号归 userid，无账号用 device_id；移动端无账号比例更高，更不能丢掉 device_id
