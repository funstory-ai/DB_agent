# 新装突增是否来自 iOS（及集成流量踢除）

- **需求编号**: T028
- **规范大类**: `anomaly`
- **状态**: 进行中（平台结论 + 集成画像/激活/踢规则已出；待确认是否写 pitfalls / 正式改口径）
- **日期**: 2026-09-01
- **定稿 SQL**: 对话探查；`scripts/_probe_t028_*.py`（非正式，任务收工后清）
- **TASK 补丁（剔集成）**:
  - 初版（仅 Safari）：`sql/reports/dashboard_t028_exclude_embed_event_device_count_etl.sql`
  - **现行 Rule A**：`sql/reports/dashboard_t028_ruleA_embed_kick_etl.sql`（§0–§7：回填 7/28–9/01 + 重建两 TASK）

## 初始需求

1. 最近新装多了很多。新装：`init_page_daily` × `is_new_user_today='1'`。是否 iOS？
2. 深挖：是否被集成？激活率是否很低？有没有办法踢掉？

## 口径

- 表：`immdata.user_behaviour`
- 过滤：`event_name='init_page_daily' AND is_new_user_today='1'`
- 主体：`COUNT(DISTINCT device_id)`
- 平台：`LOWER(TRIM(os_name))='ios'`
- **疑似集成段（踢规则 · Rule A）**：
  ```text
  install_from = official_userscript
  AND (
    (os_name = ios   AND browser_name = Safari)
    OR (os_name = macos AND browser_name = Maxthon)
  )
  ```
  保留 `browser_name LIKE 'Imt%'` 的原 App userscript（激活率 ~85–90%）
- **3 日激活（非正式抽样）**：安装后 3 日内出现任一翻译类事件  
  `translate_page` / `translate_video_subtitle` / `use_ai_subtitle` / `translate_image` / `translate_manga` / `selection_translate` / `translate_input` / `translateTextInSidePanel`  
  样本：`xxhash64(device_id)%50=0`（约 2%）

## 主结论

### 1）平台：整体抬升主要由 iOS

| 月 | iOS 新装设备 | 全平台新装设备 | iOS 占比 |
|----|--------------|----------------|----------|
| 2026-06 | 93,011 | 2,909,744 | 3.2% |
| 2026-07 | 154,283 | 3,010,139 | 5.1% |
| 2026-08 | **502,397** | 3,470,990 | **14.5%** |

- 跳变起点约 **2026-07-28**；6→8 月全平台增量中 iOS 约占 **73%**。

### 2）根因画像：极像 userscript / 网页集成，而非原生 ImtiOS App

跳变前后交叉（设备数）：

| cohort | 主组合 | 设备数（示意） |
|--------|--------|----------------|
| pre（7/1–7/27） | `official_userscript` × `ImtiOS_*` | ~5.2 万（主导） |
| pre | `official_userscript` × `Safari` | **1,290** |
| surge（7/28–8/10） | `official_userscript` × `Safari` | **197,873** |
| surge | `official_userscript` × `ImtiOS_*` | ~2.9 万 |

- `install_from=safari`（真 Safari 渠道）在 surge **未暴增**（反而略降）。
- `official_jssdk`×Safari 仅数百级，不是主量。
- surge 的 `official_userscript`×Safari 版本几乎全是 **`1.27.1`**（约 19.7 万 / 19.8 万）。
- 与插件侧「userscript / jssdk / sdk-lite 握手嵌入」形态一致；`browser_name=Safari` + `official_userscript` 更像网页侧上报，不是 `ImtiOS_*` App UA。

### 3）激活率：按看板口径，**不踢时明显不对**

**激活** = 当日 `translate_page` 且 `is_new_user_today='1'`（**不是**安装后 3 日多事件；此前 T028 探查用错口径，作废）。

筛选 `browser_name='Safari'`（全平台，与截图 DAU ~29k 对齐）：

| 日 | 新装 | 激活 | 激活率 | 剔集成后新装 | 剔集成后激活 | 剔集成后激活率 |
|----|------|------|--------|--------------|--------------|----------------|
| 7/24 | 1,459 | 1,162 | 79.6% | 1,321 | 1,078 | 81.6% |
| 7/27 | 1,377 | 1,089 | 79.1% | 1,274 | 1,031 | 80.9% |
| 7/28 | 5,390 | 1,336 | **24.8%** | 1,307 | 1,025 | **78.4%** |
| 7/30 | 19,021 | 1,880 | **9.9%** | 1,207 | 951 | **78.8%** |
| 8/03 | 16,402 | 1,681 | **10.3%** | 1,469 | 1,073 | **73.0%** |

- **不踢**：新装阶跃、激活率从 ~79% 跌到 ~8–10%——与你截图一致，**谈不上平滑**。
- **剔集成**（`install_from=official_userscript` × `browser_name=Safari`）：新装回到 ~1.2k–1.5k/日，激活率回到 ~78–82%。
- 此前说的 **remain** = 「剔除上述集成设备后的剩余设备」，表述不清，以后改用 **剔集成**。

对比：`install_from=safari`（真 Safari 渠道）7/28 前后新装 ~1.1k、激活率 ~82%，本身一直平滑——暴量的是 userscript×Safari 浏览器维，不是 Safari 扩展渠道。

定稿 SQL：`sql/reports/anomaly_t028_safari_new_install_activation.sql`；口径 **P034**。

### 4）可踢：规则清晰，误杀在跳变前极低

**推荐规则（看板/新装分母）：**

```text
os_name = ios
AND LOWER(TRIM(install_from)) = 'official_userscript'
AND TRIM(browser_name) = 'Safari'
```

可选加严（几乎不改踢出量）：`AND version = '1.27.1'`。

| 窗 | iOS 设备 | 命中踢规则 | 占比 |
|----|----------|------------|------|
| pre 7/1–7/27 | 87,152 | 1,290 | **1.5%**（误杀上限参考） |
| surge 7/28–8/10 | 243,269 | 197,873 | **81.3%** |
| **2026-08 整月** | 502,397 | **410,954** | **81.8%**；剩 **91,443** ≈ 跳变前量级 |

### 5）踢后平滑性（看板口径 P034）

- **新装/激活率（不剔集成）**：7/28 起新装暴、激活率 ~79%→~10%，**不平滑**。
- **剔集成后**：新装 ~1.2k–1.5k/日、激活率 ~78–82%，与 7/24–27 同量级。
- 日活（translate_page UV）跳变前后 ~2.5万–3万，本身平稳。

## 【异常审查】iOS 新装突增 — 疑似集成 userscript

- 涉及表/字段：`user_behaviour`：`event_name` / `is_new_user_today` / `os_name` / `install_from` / `browser_name` / `version` / `device_id` / `created_ts`
- 观察窗口：2026-06～08；画像对比 7/1–7/27 vs 7/28–8/10；激活抽样 7/21–8/3
- 举例（可复核）：
  - 2026-07-20：iOS 新装 ~3k（常态）
  - 2026-07-28 起阶跃；surge 段 `official_userscript`×`Safari`≈19.8 万，版本几乎全 `1.27.1`
  - 8 月踢规则命中 410,954 / 502,397 ≈ 81.8%
- 规模与占比：见上表；激活率 kick≈1.2% vs App≈4.9%（2% 抽样）
- 影响哪个指标：凡用该新装定义的新装/激活/转化分母（会虚高新装、拉低激活）
- 建议动作：统计口径剔除上述规则；产品侧核对接站点/SDK 白名单与 `1.27.1` 发布时间
- 是否写入 pitfalls：**待确认**

## 需求覆盖对照

| 条目 | 结果 |
|------|------|
| 新装是否增多 / 是否 iOS | ✅ 主因 iOS，7/28 起跳 |
| 是否被集成 | ✅ 高度疑似 `official_userscript`×Safari（非 App、非官方 safari 渠道） |
| 激活是否很低 | ✅ 相对 App 约 1/4（抽样非正式） |
| 能否踢掉 | ✅ 可用规则；8 月可踢 ~82%，pre 误杀参考 ~1.5% |
| 踢后是否平滑 | ✅ **剔集成后**新装+激活率平滑；**不剔**则激活率仍 ~10% |
| 写仓补丁验收（2026-09-02） | ✅ 初版 7/28–8/31 回填 + TASK 含 Safari embed；✅ **9/1 补洞** |
| Rule A 扩踢 Maxthon（2026-09-02） | ✅ TASK Started（含 ios×Safari + macos×Maxthon）；Safari 平滑；Maxthon 暴量日≈0；与 behaviour 对账差 ≤3；无 grain 叠层 |
| 剔后全平台仍 36%→31% | ✅ **主表体量上几乎全是 Windows**（约 −4.9pp / 总 −5.3pp）；Android/iOS/macOS 对 headline 可忽略 |
| 近期版切片里的 Android −31pp | ⚠️ **不能拿来解释 headline**（移动端体量不够）；那是 1.30+ 子总体的另一现象 |
| 剔僵尸后仍跌的根因（停挖旧版） | ✅ 见「贡献度拆解」：headline −5.25 中 Windows −4.32；近期残差上 **zh-CN 界面**会计主因；**US×en** 反事实约挽回近期 4.8pp / 全平台 ~0.9pp（IP 因 VPN 仅参考） |

## 贡献度拆解（2026-09-02，Kitagawa + 反事实）

观察窗：midJun（6/10–6/20）vs lateAug（8/20–8/30）。全平台 Rule A 后：**36.29% → 31.04%（−5.25pp）**。

**梯子说明**：用户多用 VPN，`real_geo` 仅作参考，不作为根因定案；界面语言更稳。  
**两种算法**：① Kitagawa 本格（各切片 mix+rate，加总闭包）；② 反事实「若该切片占比+激活率冻结在 midJun」可挽回多少（扩量稀释会算进该切片）。

### A. 全平台 −5.25pp（闭包）

| 问题点 | 对全平台贡献 (pp) | 备注 |
|--------|-------------------|------|
| **Windows** | **−4.32** | 占比略升 +0.56，组内激活率掉 −4.89 |
| Android | −0.43 | |
| iOS | −0.28 | |
| macOS | −0.22 | |
| 其它 | ≈0 | |
| **合计** | **−5.25** | |

### B. Windows 内 −6.19pp（折合全平台约 −4.9pp 的 rate 路径）

| 问题点 | 对 Windows (pp) | 折合全平台 (pp) |
|--------|-----------------|-----------------|
| **Chrome** | **−4.61** | **≈ −3.64** |
| Electron | −1.17 | ≈ −0.92 |
| Edge | −0.37 | ≈ −0.29 |

### C. Win×Chrome×chrome_store −8.34pp（约占 lateAug 全平台新装 ~44%）

| 问题点 | 对渠道 (pp) | 折合全平台约 (pp) |
|--------|-------------|-------------------|
| **recent（1.30–1.32）** | **−4.66** | **≈ −2.1** |
| **other_ver（非僵尸非近期）萎缩** | **−4.99** | **≈ −2.2** |
| zombie 本格 | +1.31 | ≈ +0.6（挤占效应体现在上两行的负 mix） |

### D. 近期版残差 −8.0pp（已剔僵尸；VPN 注意）

#### D1. 按 `interface_language`（推荐，不依赖 IP）

| 问题点 | Kitagawa 本格 (pp) | 反事实冻结占比+率可挽回 (pp) |
|--------|-------------------|------------------------------|
| **zh-CN** | **−8.28** | **≈ +5.8**（折合全平台约 **+1.0**） |
| en | +1.31 | ≈ +4.2（折合全平台约 **+0.7**） |
| other | −0.72 | — |
| 合计 | ≈ −7.7（与 −8.0 同层） | |

→ **不靠 IP 时：会计主因是 zh-CN 高激活段变少+组内变差**；全球 en 扩量也有稀释，但本格正贡献来自「低激活段变大」的记账方式。

#### D2. 你问的「美国 IP × 界面 en」（IP 不可靠，仅参考）

| 算法 | 对近期版 −8.0pp | 折合全平台约 |
|------|-----------------|--------------|
| Kitagawa 本格 **US×en** | **仅 −0.26** | ≈ 0 |
| 反事实：仅冻结 US×en **激活率** | 挽回 **+1.92** | ≈ **+0.3** |
| 反事实：仅冻结 US×en **占比** | 挽回 **+3.47** | ≈ **+0.6** |
| 反事实：冻结 US×en **占比+激活率** | 挽回 **+4.79（约 60% 近期残差）** | ≈ **+0.9** |

同层其它格（参考）：US×nonEn **−2.89**；exUS×en **+1.57**；exUS×nonEn **−6.44**（Kitagawa 最大负项）。

**读法**：Kitagawa 把「US×en 变多挤掉高激活用户」记在其它格的负 mix 上，所以 US×en 本格只有 −0.26；要回答「这块坏了多少」应看反事实 **≈ 挽回 4.8pp 近期 / ~0.9pp 全平台**，不是主因到能解释清 headline −5.25。

