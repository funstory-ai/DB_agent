# 检验：`imt_userinfo.createtime` 能否代替/补充 installtime

- **需求编号**: T023
- **规范大类**: `anomaly`
- **状态**: ✅ 已完成
- **日期**: 2026-08-31
- **定稿 SQL**: `sql/reports/anomaly_userinfo_createtime_check_20260831.sql`
- **背景**: 设备 `installtime` 不可靠（迟补上报）；评估账号 `createtime` 准不准、能否替代安装时间。

## 需求覆盖对照

| 需求项 | 状态 |
|--------|------|
| createtime 字段质量 | ✅ |
| 与订单/设备/行为交叉验证 | ✅ |
| 能否代替 installtime | ✅ 不能代替；可作账号级新用户锚点并辅助剔老客 |

## 【异常审查】userinfo.createtime

- **涉及表/字段**：`imt_userinfo.createtime`；订单；`imt_deviceinfo.installtime` / `usercreatetime`；短窗 `user_behaviour.ex_int_arg1`
- **规模与结论**：

### 1. 字段本身

| 检查 | 结果 |
|------|------|
| 空值 / 1970 | **0**（712 万活账号） |
| 时间范围 | 最早 2023-08-11（与表文档「约 2023-08 起有数据」一致） |

### 2. 与商业行为（2026-08 新注册 265,775）

| 检查 | 结果 |
|------|------|
| 有 finished 订单 | 14,407 |
| 其中首单在注册后 1h 内 | **12,152（84%）** → 注册与试用/下单衔接正常 |
| 现金早于账号（>5min） | **35（0.013%）** → 脏数据极少，过滤即可 |
| 2026-01～08 按月 | 现金早于账号均约 **0.01%～0.02%** |

### 3. 与设备表

| 检查 | 结果 |
|------|------|
| `deviceinfo.usercreatetime` vs `userinfo.createtime` | 有值时 **≈100% 差 ≤5min**（镜像字段，可信） |
| 8 月「min(install)」userid：注册与 install 差 ≤1h | **82.1%** |
| 同批：install 远早于注册（>1 天） | **6.8%** → 先装后注册，两套时间本就不同 |
| 同批：账号早于 install ≥180 天 | **0.6%** → 迟补上报老号，应用 createtime 识别 |

### 4. 与登录后行为（非正式短窗：8/1～8/7 新注册）

| 检查 | 结果 |
|------|------|
| 账号数 | 71,374；窗内有 `translate_page`（ex_int_arg1）52,174 |
| 行为早于账号 | **0** |
| 注册后 1h 内首条翻译 | 44,229 / 有行为者中多数 |

- **举例（现金早于账号，应剔）**：userid=`6987484`，账号 2026-08-12，首现现金 2024-03（Apple 隐藏邮）
- **能否代替安装时间**：**不能**。8 月新注册里，有设备者约半数 `min(install)` 早于 `createtime`（先装后注册/设备先报）。`createtime` = **账号出生**；`installtime`（即便准）= **安装/上报**。二者场景不同。
- **建议动作**：
  1. 账号级「新用户」用 **`userinfo.createtime`** 作主锚点（质量足够）
  2. 硬过滤：现金早于 `createtime−ε`（ε=5min）
  3. 辅助剔「install 扮新装」：`createtime` 已 ≥30 天却 min(install) 落在近窗 → 不当新装
  4. **不要**用 createtime 填补/冒充 installtime 做设备新装漏斗
- **是否写入 pitfalls**：待与「账号级新用户」规范一并确认

## 一句话结论

**`userinfo.createtime` 作为注册时间可信（空值/1970 无；与订单、登录行为、device.usercreatetime 一致；现金早于账号仅 ~0.01%）。不能代替 installtime，但适合做账号级新用户锚点，并用来识别「老号 + 迟补 install」。**
