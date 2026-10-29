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

### P013 — 付费和试用分开；兑换码算付费
- 发现日期：2026-08-12（纠错）；补充：2026-08-13；2026-10-16 写明兑换码算付费
- 涉及：`imt_subscriptiongoodsorder`
- 正确做法 / 规避：
  - **付费**、**试用**是两类，不能混在一个数里。
  - **付费** = `orderstatus='finished'`，并且下面任一成立：
    1. `COALESCE(amountpaid,0)>0`（应用内付款）
    2. **兑换码**（淘宝等站外买的会员。钱不在 `amountpaid` 里，订单金额经常是空）
  - **兑换码**两条都要认，缺一就会漏：
    - `LOWER(ordertype)='code'`
    - 或 `subscriptiongoodssnap` 里 `SubscriptionType` 以 `onetime` 开头（`onetime_3day` / `onetime_7day` / `onetime_yearly`）
    - 识别：`CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'`
  - **试用** = `finished` 且 `COALESCE(amountpaid,0)=0`，并且**不是**兑换码。常见 `ordertype` 为 `trial` / `iospay_trial` / `googleplay_trial`，`trialperioddays=3`。
  - 兑换码金额为空，不是试用，也不是「0 元单」。0 元且不是兑换码的，才是试用。
  - 不要只用 `ordertype LIKE '%trial%'` 定试用；也不要只用 `amountpaid>0` 定付费（会把淘宝兑换码漏掉）。
  - 默认不必再问「兑换码算不算付费」。用户另定排除时才排除。

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
  - **E 同一设备多行账号（2026-10-16，T070）**：`row_number` 去重必须有唯一决胜键。同一 `deviceid`、同一 `installtime`、多个 `userid` 时，只按 `installtime` 排序会每次留下不同账号。设备粒度「这台付过费」= 挂着的**任一**账号有付费单（P013），这台算 1。禁止只认随机留下的那个账号。反例：三台设备两行安装时间相同，累计付费在 52 / 50 / 49 之间跳，订单行数没变

### P019 — 抽样复核：目的是验 SQL，禁止为抽样重跑全量；指标随任务变
- 发现日期：2026-08-13（任务一抽样实践）
- 涉及：交付前抽样；`docs/sample_validation.md`
- 现象：任务一为抽 N=20，先对 3 万+ cohort 重算全量翻译次数再建分层池，单次耗时十余分钟；叠加防 OOM 的「每设备拆 5 次 COUNT」后更慢。若照此模式，后续任务可能「光抽样抽一小时+」。
- 根因：
  1. 把「分层标签」算在全量结果上，等价再跑一遍主报表
  2. 误把「翻译五类次数」写成通用硬性标准（转化率等任务并不适用）
- 正确做法 / 规避：
  - **目的**：抽几个样本，用**另一条更窄的路径**核对主 SQL 有没有算错；**同时**判断交付数字是否合理；不是再产一份全量数
  - **核对字段随任务定**：次数任务对次数；转化率对「是否分母/分子归属正确」；漏斗对关键节点。禁止默认永远验翻译次数
  - **数字合理性（与对拍并列，2026-10-12 补强）**：仅验 null/门闩/加总不够。须扫：假零（已闭合窗却 0%）、实验串组、量级/组间关系、相对上版离谱漂移。反例：T064 首版 W1 写死周上界，09/28 周 W1=`0.00` 非 null，门闩断言放过
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
  1. **时间窗、事件范围、是否活跃、去重主体**等易分歧点：需求未写清 → **先问再查**。兑换码算不算付费已由 P013 拍板，不必再问。
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
  - 与 P013 同一套：付费含兑换码；试用是 `amountpaid=0` 且不是兑换码。本条只管有效期 / 流失。

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
  - 「新用户漏斗」→ 只用 P034/`is_new_user_today`，**新付费墙类却未套 P039**（2026-09-30 起默认必须剔，勿再问）
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
- **与 P039**：设备级 P034 激活 cohort 上「剔重装老号」用 **P039（1 天缓冲）**，不要套本条的 30 天账龄当默认设备分母刀
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
- **与「真·新账号」区分**：`is_new_user_today=1` 是插件侧新装日，含重装老号（约 5%～7%，**P039**）。**新付费墙类主交付默认套 P039，不必再问**；一般看板/历史 AB 仍可主用本条纯 P034

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

### P038 — 中间表 / 看板 TASK：Cron 必须晚于上游日更（勿「今天跑了仍停在上上周」）
- 发现日期：2026-09-28（T025 分业务周留存看板）
- 涉及：下游留存/汇总 TASK × 上游周表/日表 TASK（例：`update_imm_translate_biz_firstuse_weekly_retention` ← `update_imm_device_event_by_utf8_week`）
- 现象：
  1. 今天周一、下游 TASK `last_success` / `update_time` 已刷新，但看板最新 cohort 仍是**上上周**
  2. 最新一周有规模、**W1（及后续窗）全 0**，像「没算留存」
- 举例（T025，北京 2026-09-28）：
  - 上游周表 Cron：`0 2 0 * * 1` **UTC** ≈ 北京 **08:02**；当日 `max(week_start_day)=2026-09-21`
  - 原下游留存 Cron：`0 0 6 * * 1` **Asia/Shanghai** = 北京 **06:00**（早于上游 ~2h）
  - 06:00 全量重算时源表尚无 09-21 → 留存 `max_cohort=09-14` 且该周 W1=0；08:02 上游写入后下游要等下周一才再跑 → **永久落后约一周**
- 根因：建看板只定了「每周一跑」，**没核对上下游 Cron 的绝对时刻与时区**（UTC vs Asia/Shanghai 差 8 小时，极易排反）
- 正确做法 / 规避：
  1. 写仓前列出链路：`源行为/订单 → 上游日/周表 TASK → 本看板中间表 TASK`，查 `SHOW TASKS` 的 **schedule + 时区**
  2. 下游 Cron **必须晚于上游**（留足跑完缓冲；周更建议上游后 ≥1～2h，如上游≈周一 08:02 北京 → 下游 **10:00 上海**）
  3. 验收新鲜度（与 P027 并列）：`MAX(下游业务周/日) = MAX(上游源表业务周/日)`；**禁止**只看 TASK Started / `update_time` 已变
  4. 抽最新 cohort：未满窗允许 Wn=0，但**上一段已闭合窗**应对得上源（如最新周的上一周 W1>0）
  5. 修调度时：改 Cron + **立刻全量重算一次**（否则要再等一周）；补丁样板 `sql/reports/dashboard_t025_retention_schedule_fix_20260928.sql`
- 关联：P022（中间表+TASK）、P027（新鲜度）、P028/P035（TASK 写法/六段 cron）；`docs/norms/dashboard.md`「上下游调度」

### P039 — 设备级 P034「新装/激活」≠ 真·新账号；重装老号须另剔（1 天缓冲）
- 发现日期：2026-09-29（T045 / T018）；**2026-09-30 默认强制**：新付费墙类主交付默认剔，**不必再问**
- 涉及：`user_behaviour.is_new_user_today`；`imt_userinfo.createtime`；`imt_deviceinfo.createtime` / `installtime`；激活锚点 `first_ts`
- **适用范围（默认要剔，替代「每次先问」）**：
  - 新付费墙 / 登录赠送额度（`login_ai_quota_gift_*`）/ 改版付费墙「对新用户」漏斗与转化
  - 旧硬墙对照里谈**新用户触墙率**等（如 T046）
  - 原则：**已拍板的新规则替代旧默认后，隔久也不要再问同一题**（场景会忘）
- 现象：
  1. 按 P034（`is_new_user_today='1'`）做新用户漏斗时，分母混入**重装/换机后登录老账号**
  2. 误以为静默领取≈老号默认领；或以为剔老号后「立即登录%」应≈「领取%」
- 举例 / 占比（T018 / T045）：激活约 **6%** 为老号设备；老号约占累计付费分子 **16%～21%**；日重装样约 **1k+/日**
- 根因：`is_new_user_today` 是插件安装日维度；`deviceinfo` 时间常晚于行为，不能用来判老号；严格 `< act_ts` 误伤同会话注册
- 正确做法 / 规避：
  1. **新付费墙类只出剔老号一版** = P034（或任务约定新装）+ **本条剔老号**。**不要**再单独做含老号的全量对照（口径 A）。**禁止**每次再问要不要剔
  2. **一般长期 AB/看板**（纯与历史 P034 对齐）：可主用未剔；一旦需求写成「新用户效果」则改用本条
  3. 刀法：userid（`deviceinfo` ∪ 激活 `ex_int_arg1` ∪ 本题 claim）满足 `imt_userinfo.createtime < first_ts − 1 天` → 整台设备剔除
  4. ❌ 勿用 deviceinfo 时间判老号；❌ 勿把 gift「立即登录%」当领取上界
  5. 与 **P033**（账号级三过滤）勿混用
- 复用：`query_paywall_ab_*excl_old*`；`query_login_ai_quota_gift_weekly_*`（`B_excl_old_acct` / v1333）
- 关联：T018、T045、T046；`docs/norms/query.md`；表文档「勿想当然」

### P040 — AB / 实验查数必须限定版本（勿把老客户端当实验流量）
- 发现日期：2026-09-30（T047/T048；用户要求写入规范）
- 涉及：`user_behaviour.version`；`ab_tag`；实验上线版本；Rule A（T028）之外的「脏分母」
- 现象：
  1. 很老版本（如 1.18 / 1.26 / 1.31）仍可带 `ab_tag`，但**未跑当期实验 UX**（配置/决策链不同），进 AB 分母等于掺集成/旁路流量
  2. 字符串比较 `version >= '1.32.6'` **错误**：`'1.32.10' >= '1.32.6'` 为假，T018 旧滤会**漏掉约 4.9 万**合法 1.32.10 激活
- 正确做法 / 规避（**AB 类默认强制，不必再问要不要限版本**）：
  1. 写清 **实验起始版本**（优先）或 **近 N 个发布版本**白名单；任务文档与 SQL 注释写明
  2. 用 **major/minor/patch 数值比较**或精确 `LIKE '1.32.%'` + patch 条件；❌ 禁止单靠字典序 `version >= 'x.y.z'`
  3. 「污染」不只 Rule A：老版本 + 未声明版本上界/下界都算；Rule A 仍按 P034/T028 另剔（若本题需要）
  4. 新付费墙/登录赠送等「对新用户」实验：与 **P039 剔老号**叠用（T048：版本≥起始 + 剔老号）
  5. 版本说不清 → 查插件仓/任务文档实验上线版；仍不清再问用户（P025）
- 复用：`query_paywall_ab_longterm_ver_excl_old_20260930.sql`（≥1.32.6 语义化 + P039）
- 关联：T018、T047、T048；`docs/norms/query.md`

### P041 — 核心月报版式对齐上月截图（标题加粗、指标分行）
- 发现日期：2026-10-08（T058；用户给 08 月截图定样板）
- 涉及：月报交付正文；不含任务核对表
- 现象：粘成段、乱加粗数字、把「整体来看/注」拆碎，与上月飞书正文不一致
- 正确做法 / 规避（**月报类强制**）：
  1. **只加粗**大标题 + `1、`/`2、`/`3、`；正文数字不加粗
  2. 段内指标各占一行、中间不空行；段与段之间空一行
  3. 「整体来看…」「注：…」各一整段不拆
  4. **段末汇总按当月重写**：结合环比翻转、结构矛盾、季节/大促；禁止换数字照抄上月套话
  5. 主交付 `.docx`；细则 `docs/norms/query.md`「月报正文格式」
- 关联：T031、T058

### P042 — 行为点击→订单漏斗：订单时间可相对点击前放宽（默认 1 天）
- 发现日期：2026-10-10（T062；用户确认写入规范）
- 涉及：埋点点击/弹窗主按钮 → `imt_subscriptiongoodsorder` 归因；付费墙「去付费」等条件转化
- 现象：埋点与订单落库有前后时差，严格 `订单 createtime >= 点击 ts` 会漏掉「先成单、点击略晚入库」或时钟偏差的真实付费
- 正确做法 / 规避（**点击→订单类漏斗默认**）：
  1. 归因下界默认：`订单.createtime >= 点击时间 − 1 天`；上界仍受观察窗 / asof 约束
  2. 任务文档与 SQL 注释写明「P042 前放宽 1 天」；若业务要求严格因果再收紧并注明
  3. 适用于：耗尽/墙「去付费」→付费、同类 CTA→成单漏斗；**不**改写无点击锚点的累计付费分母（总付费仍按原激活锚点窗）
  4. 放宽只消化时差，**不是**把点击前任意久的老单算进漏斗；仍剔锚点前老客（T018）
- 复用：`query_login_ai_quota_gift_weekly_ge1332_20261010.sql`（`exhausted_pay_then_paid`）
- 关联：T062；`docs/norms/query.md`

### P043 — 结论必须有证据；猜测不能当成答案
- 发现日期：2026-10-15（T072；用户确认写入规范）
- 涉及：一切对用户交付的判断（口径、原因、同步、源库、支付后台）
- 现象：T072 把 Databend 副本 `MAX(createtime)` 停在凌晨说成「同步停更」，并进一步猜「源库是真没有新单还是同步没写过来」。本仓碰不到 MySQL；订单等业务表经 `H:\imt_data_synch` **北京每天 01:00** 日更，凌晨水位是正常现象。埋点仍在更新也不能证明业务表故障（另一条链路）。
- 正确做法 / 规避（**强制**）：
  1. 写成结论的句子，必须能指到证据：SQL 结果、表文档、插件代码、`H:\imt_data_synch` 调度、或用户原话。没有证据就写「未查到 / 不知道」，不要补一个听起来完整的原因。
  2. 可以提出猜测，但必须同时写出三件：这是猜测、依据是哪几条已经看到的事实、还缺什么才能证实。禁止用猜测收束成定论。
  3. 碰不到的系统不要判断它里面有什么：MySQL 源库、同步作业成败、支付后台。副本时间水位先对同步节奏，再谈异常。
  4. 业务表日更（`imt_data_synch`，北京 `0 1 * * *`）与 `user_behaviour` 埋点不是同一条管道，不能互相证明对方停了。
  5. **付费前出现过的事件不是付费原因。** 登录墙、去登录不是付费原因。归类只跟决定性的那一条事件；序列里另有个人页或升级入口，不得改标签。
  6. 代码里的条件必须保留，不能说成所有人都会。没有耗时埋点，不要说某次请求很慢。
  7. 反例（T070，2026-10-16）：登录墙、个人页被写成付费原因；「非会员且选 Pro、客户端剩余 &lt; 100 才拦」被说成所有非会员都会弹升级墙。
- 关联：T072、T070；`.cursor/rules/no-ungrounded-claims.mdc`

### P044 — 已交付的一个数字，必须来自同一次结果
- 发现日期：2026-10-16（T070；用户确认写入）
- 涉及：同一张表、同一个格子的多次查询；Excel 与重跑；设备粒度与账号粒度
- 现象：10/12–16 新墙累计付费已交付 **52**（设备、真实激活日、含兑换码）。另一次用「付款时间 − 四舍五入的激活后小时」倒推出 58 个账号，被说成同一格。同一段代码重跑成 50、再成 49，又用新数替换 52。再用重跑里「没有耗尽墙的 42」去减 52。
- 根因：解释某一个格子时换成了另一次查询、另一种粒度或另一个时间锚点
- 正确做法 / 规避（**强制**）：
  1. 对外解释某一个已交付数字，必须用**同一次查询、同一粒度、同一时间锚点、同一人群**
  2. 重跑变了：先对出多出来或少掉的行，再决定是否替换已交付的数。输入没变而人数变了，先当取数错误
  3. 禁止用另一次跑的子集去减旧总数
  4. 禁止用倒推锚点的另一批人顶替这一格
- 关联：T070；P018-E、P013

### P045 — 追踪/同期群数据（留存/回访周/cohort）禁止写死；recurring 刷新须由数据推导
- 发现日期：2026-10-26（T085 复盘；用户明确要求写入规范）
- 涉及：新付费墙周漏斗（T077/T084/T085）等 recurring 快照；`export_t0xx_gift_weekly_funnel_*.py` 的 W1/留存；所有按 cohort/回访周出留存的刷新脚本
- 现象：刷新到新 asof 后，新一周的 W1/留存永远是空。根因是回访周/回访人群被硬编码在某一批（如 `week_start_day = DATE '2026-10-12'`、`install_day < '2026-10-12'`、`key=='w_1010_1011'` 才显示 W1），刷新时回访周不随 asof 推进。
- 举例：T077(10-20) 只给 10/10–11 算 W1；T084/T085 初版沿用同一硬编码，10/12–18 回访周已落在 asof 内却仍是空；10/19–25 那批回访周 10/26 起、未成熟，应留空（是对的）。
- 占比：每刷一次就「丢」一整周已成熟的留存；历史周分母因剔老号层回填还会小幅收敛（<0.2%，见 MEMORY.md「分母漂移」）。
- 根因：把「首版只有某批满 7 天回访，故只算它」的临时设定固化成了常量，而非「按各 cohort 各自回访周独立计算、回访窗完全落在 asof 内才收口」。
- 正确做法 / 规避（**强制，对 recurring 追踪类刷新**）：
  1. **留存/回访周必须由数据推导**：回访周 = 激活区间结束日的当周周一（`monday_on_or_after(end)`）；成熟度 = cohort 最后激活日 +7 天 ≤ asof（标准 W1 口径，允许最后一天尾段数小时未入库）；未成熟则留空（不是 0）。
  2. **recurring 脚本不留任何写死的周/日期/切片 key**：asof、各 cohort 的回访周、显示条件都应是输入或派生，而非常量。
  3. 与旧墙 AB 刷新手册一致：`query_paywall_ab_20260821.md` §下次刷新要求 `week_active` 的 `week_start_day` 上界「必须改成新的 `last_closed_week_start`，漏改会把刚闭合的留存算成 0%」。本坑是更彻底的版本——整段写死而非只漏改上界。
  4. 与 P019 关联：P019 已把「T064 首版 W1 写死周上界」列为抽样合理性反例（已闭合窗却 0%）。本坑同根。
  5. 与 P029/P038 同一原则：追踪类数据用滚动窗，禁止写死日期上界。
  6. 验收：刷新后，刚闭合的那一周 W1 应非 null 且 >0；用 P019 合理性扫「已闭合窗却 0%」假零。
- 关联：T077/T084/T085；P019、P029、P032、P038；旧墙 AB 刷新手册 `query_paywall_ab_20260821.md` §下次刷新

### P046 — 订单币种匹配不到汇率表时，收入按「标准人民币价」计（不丢、不置零）
- 发现日期：2026-10-26（T 未立项；用户明确要求写入规范）
- 涉及：`imt_subscriptiongoodsorder.currency` × `immdata.exchangerates`；一切收入折算 / 人民币汇总
- 现象：订单币种与 `exchangerates` 匹配不上时，若任其 `LEFT JOIN` 得 `NULL` 再乘汇率，该笔收入变 `NULL`/`0`，低估收入或漏单。
- 根因（2026-10-26 核查，`imt_subscriptiongoodsorder` isdeleted=0）：
  1. **大小写**：订单主币种存小写（`usd/cny/eur…`），汇率表大写（`USD/CNY/EUR…`），精确 join 直接失配——这是**最大头**（约 74 万订单行）。主修复是 join 用 `UPPER(o.currency)=e.currency`，**不是**加小写副本。
  2. 部分真实 ISO 币种未维护（IQD/CZK/COP/MNT/RON/UAH/DZD/PKR/MAD/CRC/ARS/LKR/GEL/PYG/GHS/TZS/JOD/RSD/BOB/XOF/UZS/BGN/KES/AZN/XAF/BDT，共 26 个）。
  3. 币种字段写着字符串 `'None'`（空值被串成字符串，上游数据质量问题，11,855 付费单 / 75,834 行）与两位国家码（`US/TW/HK/JP/KR…`，写错码、非真实币种）。
- **正确做法 / 规避（强制）**：
  1. **主路径**：`LEFT JOIN immdata.exchangerates e ON UPPER(o.currency) = e.currency`，取 `exchangerate`（基准 CNY，`CNY=1.0`；**注意 JPY/KRW 是「每 100 单位」**，其余多为每 1 单位）。
  2. **匹配不到的币种，收入直接按「标准人民币价」（标准收入）计入，禁止把该笔置 `NULL`/`0` 丢掉。** 例：一个月会员标准价 ¥N，匹配不到的月会员订单直接按 ¥N 算收入。
  3. 「标准收入」= 该商品的标准人民币标价（由产品定价给定，如月会员 ¥N / 年会员 ¥M），**不依赖订单自身币种的金额**；分析侧按商品类型（`subscriptiontype`/`membership`/`dateperiod` 等）引用对应标准 CNY 价。
  4. **匹配不到的范围** = `UPPER(currency)` 仍不在 `exchangerates`（含 `'None'`、两位国家码、未维护真实币种）。其中 `'None'` 与两位码是上游写错，单列处理、不强行加汇率；26 个未维护真实币种按 `sql/reports/probe_add_missing_currency_rates.sql`（提案，手工维护表，禁止只读代跑）补。
  5. **量级**：未维护的 26 个真实币种累计仅 ≈¥16.9k/595 天（≈¥28/天），近 90 天 ≈¥81/天；用标准价近似的误差可忽略。但 `'None'` 量更大（11,855 付费单），属数据质量、优先上游修，规范上仍按标准价计入而非漏掉。
  6. 兑换码（`amountpaid` 为空，P013）不算「匹配不到汇率」的折算问题，仍按 P013 计为付费。
- 示例 SQL（收入折算，匹配不到→标准价）：
```sql
-- std_cny_price 为该商品的标准人民币标价（按产品类型引用，此处以 CASE 示意）
SELECT
  o.currency,
  COALESCE(e.exchangerate, 0)                          AS matched_rate,
  CASE
    WHEN e.exchangerate IS NOT NULL
      THEN (o.amountpaid/100.0) * e.exchangerate        -- 匹配：本位币÷100×汇率
    ELSE std_cny_price(o)                               -- 不匹配：标准人民币价
  END                                                  AS revenue_cny
FROM immdata.imt_subscriptiongoodsorder o
LEFT JOIN immdata.exchangerates e
       ON UPPER(o.currency) = e.currency
WHERE COALESCE(o.isdeleted,0)=0 AND o.orderstatus='finished'
  AND COALESCE(o.amountpaid,0) > 0;
```
- 关联：P008（单位/币种）、P013（付费含兑换码）、P043（结论有证据）；表文档 `docs/tables/immdata/exchangerates.md`；补齐提案 `sql/reports/probe_add_missing_currency_rates.sql`

### P047 — Max 会员含大量「存量升级补差价」，不能当全新年费/新增收入
- 发现日期：2026-10-29（用户明确要求写入规范）
- 涉及：`imt_subscriptiongoodsorder`（`membership='max'` / `subscriptiontype LIKE 'max%'`）；Max 档收入 / Max 新增订阅 / Max 年费统计
- 现象：
  - 选 `membership='max'`（或 `subscriptiontype LIKE 'max%'`）当「Max 会员 / Max 年费」时，会把**从已有会员升级上来的人**算成「全新年费」买家；且单笔 `amountpaid` 只是**差价**，不是 Max 全价。
- 举例 / 证据（2026-10-29 查 `imt_subscriptiongoodsorder`，`finished` + `COALESCE(isdeleted,0)=0`）：
  1. **升级比例（保守下限）**：有 Max 付费单的 `userid` 共 **5,844**；其中 **1,645** 个在首笔 Max 单之前已有非 Max 会员付费单（`monthly`/`yearly`/`two_yearly`，`amountpaid>0`）= **28.15%**。未含「试用转正」「兑换码会员」「旧单已失效/换号」等，真实升级占比更高。
  2. **金额是差价（非全价）**：`max_yearly` 付费单 `amountpaid` 跨度极大——最小 **¥1.15**、最大 **¥5,988,000**；含大量 ¥1~¥500 小额（13 单 ≤¥10、111 单 ≤¥100）。全新年费不可能 ¥1.15，这些只能是补差价。`max_monthly` 同理（最小 ¥0.93）。
- 根因：升级逻辑 = 现有会员按「Max 价 − 当前剩余权益」补差价；订单 `amountpaid` 记录的就是差价，不是 Max 档全价。
- 正确做法 / 规避：
  1. **统计「Max 全新订阅 / 新增年费」须剔升级**：按 `userid` 判断「首笔 Max 单之前是否已有非 Max 会员付费/有效单」，是则归为「存量升级」，不计入「全新」。
  2. **Max 收入别拿差价当全价累加**：单笔 `amountpaid` 是差价，直接求和既不等于「Max 年费全价 × 人数」也不等于真实新增 ARPU；要看 Max 档真实价值应按 **Max 标准定价**，而非用订单差价求和。
  3. **区分两类**：首次成为会员即买 Max（无更早会员单）= 真·全新；从 `pro`/`monthly`/`yearly` 升级 = 补差价。两者人数与金额语义不同，禁止混成一个「Max 年费」数。
  4. 与 **P013**（付费/试用分开、兑换码算付费）、**P046**（金额按标准价计，但本坑是「差价」语义、非币种问题）并列。
- 示例 SQL（升级识别，只读）：
```sql
-- 升级自存量会员的 Max 用户：首笔 Max 单之前已有非 Max 会员付费单
WITH max_first AS (
  SELECT userid, MIN(createtime) AS first_max_ct
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
    AND membership='max' AND COALESCE(amountpaid,0)>0 AND userid IS NOT NULL
  GROUP BY userid
)
SELECT COUNT(DISTINCT o.userid) AS upgraded_user_cnt
FROM immdata.imt_subscriptiongoodsorder o
JOIN max_first m ON o.userid = m.userid
WHERE COALESCE(o.isdeleted,0)=0 AND o.orderstatus='finished'
  AND o.membership <> 'max'
  AND o.subscriptiontype IN ('monthly','yearly','two_yearly')
  AND COALESCE(o.amountpaid,0) > 0
  AND o.createtime < m.first_max_ct;
```
- 关联：T 待立项；复现脚本 `scripts/query_max_upgrade_share_20261029.py`
