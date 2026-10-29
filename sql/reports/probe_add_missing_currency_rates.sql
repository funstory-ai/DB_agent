-- ============================================================================
-- 提案：补齐 exchangerates 中【确实缺失】的真实币种汇率
-- 生成：_probe_currency_rate_match2.py 核查（2026-10-26）
-- 范围：imt_subscriptiongoodsorder（isdeleted=0）
-- 重要前提：
--   1. 本仓为只读账号，此文件仅为提案，禁止在此环境代跑；由 exchangerates 维护人核对后执行。
--   2. exchangerates 基准为 CNY（CNY=1.00000），字段 exchangerate = 「1 单位该币种 = 多少 CNY」。
--      注意：JPY / KRW 在表里是「每 100 单位」(JPY=4.86840, KRW=0.52279)，USD/EUR 等是「每 1 单位」。
--      下方新增币种统一按「每 1 单位」填（与 USD/EUR 多数一致）。
--   3. 下列 exchangerate 为近似参考值（基于 1 USD≈7.14790 CNY 推算），执行前务必以官方/当日汇率为准核对！
--   4. 仅列出「归一大写后仍命不中的真实 ISO 币种」。不要为大小写补小写副本（用 join 归一解决）。
--   5. 'None'（字符串空值，75,834 行）与两位国家码（US/TW/HK…）不属于真实币种，见文末 CASE 处理，不要在此加行。
-- ============================================================================

-- 缺失的真实 ISO 币种及建议汇率（CNY / 1 单位，近似，待核对）：
INSERT INTO immdata.exchangerates (currency, exchangerate) VALUES
  ('IQD', 0.0055),   -- 伊拉克第纳尔
  ('CZK', 0.325),    -- 捷克克朗
  ('COP', 0.0018),   -- 哥伦比亚比索
  ('MNT', 0.0021),   -- 蒙古图格里克
  ('RON', 1.59),     -- 罗马尼亚列伊
  ('UAH', 0.174),    -- 乌克兰格里夫纳
  ('DZD', 0.053),    -- 阿尔及利亚第纳尔
  ('PKR', 0.0257),   -- 巴基斯坦卢比
  ('MAD', 0.722),    -- 摩洛哥迪拉姆
  ('CRC', 0.0142),   -- 哥斯达黎加科朗
  ('ARS', 0.0072),   -- 阿根廷比索（波动大，务必当日核对）
  ('LKR', 0.0242),   -- 斯里兰卡卢比
  ('GEL', 2.60),     -- 格鲁吉亚拉里
  ('PYG', 0.00098),  -- 巴拉圭瓜拉尼
  ('GHS', 0.461),    -- 加纳塞地（波动大，务必当日核对）
  ('TZS', 0.0028),   -- 坦桑尼亚先令
  ('JOD', 10.10),    -- 约旦第纳尔
  ('RSD', 0.0688),   -- 塞尔维亚第纳尔
  ('BOB', 1.036),    -- 玻利维亚玻利维亚诺
  ('XOF', 0.0118),   -- 西非法郎（与 EUR 挂钩）
  ('UZS', 0.000563), -- 乌兹别克斯坦索姆
  ('BGN', 4.00),     -- 保加利亚列弗
  ('KES', 0.0554),   -- 肯尼亚先令
  ('AZN', 4.20),     -- 阿塞拜疆马纳特
  ('XAF', 0.0118),   -- 中非法郎（与 EUR 挂钩）
  ('BDT', 0.0591);   -- 孟加拉塔卡

-- ============================================================================
-- 附：推荐的收入折算 join 写法（一次性解决大小写 + 国家码 + None）
-- 说明：
--   a) UPPER() 归一，救回 usd/cny/eur… 等 739,974 行（大小写导致的不匹配）。
--   b) CASE 把两位国家码映射回正确 ISO（US->USD, TW->TWD, HK->HKD, JP->JPY, KR->KRW,
--      DE/FR/IT/ES/GR/NL/AT/FI->EUR, CA->CAD, AU->AUD, BR->BRL, MX->MXN, SG->SGD,
--      TH->THB, IN->INR, MY->MYR, VN->VND, SA->SAR, AE->AED, IL->ILS, PH->PHP,
--      TR->TRY, PL->PLN, EG->EGP, IQ->IQD, MA->MAD, NG->NGN, TZ->TZS, BY->BYN, RO->RON, ID->IDR）
--   c) 'None' / 无法识别的币种：fx_rate 置 NULL，折算时单独排除，不要瞎填汇率。
-- ============================================================================
-- SELECT
--     o.currency,
--     CASE
--       WHEN o.currency = 'None' THEN NULL
--       WHEN UPPER(o.currency) IN ('US') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='USD')
--       WHEN UPPER(o.currency) IN ('TW') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='TWD')
--       WHEN UPPER(o.currency) IN ('HK') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='HKD')
--       WHEN UPPER(o.currency) IN ('JP') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='JPY')
--       WHEN UPPER(o.currency) IN ('KR') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='KRW')
--       WHEN UPPER(o.currency) IN ('DE','FR','IT','ES','GR','NL','AT','FI') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='EUR')
--       WHEN UPPER(o.currency) IN ('CA') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='CAD')
--       WHEN UPPER(o.currency) IN ('AU') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='AUD')
--       WHEN UPPER(o.currency) IN ('BR') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='BRL')
--       WHEN UPPER(o.currency) IN ('MX') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='MXN')
--       WHEN UPPER(o.currency) IN ('SG') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='SGD')
--       WHEN UPPER(o.currency) IN ('TH') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='THB')
--       WHEN UPPER(o.currency) IN ('IN') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='INR')
--       WHEN UPPER(o.currency) IN ('MY') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='MYR')
--       WHEN UPPER(o.currency) IN ('VN') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='VND')
--       WHEN UPPER(o.currency) IN ('SA') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='SAR')
--       WHEN UPPER(o.currency) IN ('AE') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='AED')
--       WHEN UPPER(o.currency) IN ('IL') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='ILS')
--       WHEN UPPER(o.currency) IN ('PH') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='PHP')
--       WHEN UPPER(o.currency) IN ('TR') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='TRY')
--       WHEN UPPER(o.currency) IN ('PL') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='PLN')
--       WHEN UPPER(o.currency) IN ('EG') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='EGP')
--       WHEN UPPER(o.currency) IN ('IQ') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='IQD')
--       WHEN UPPER(o.currency) IN ('MA') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='MAD')
--       WHEN UPPER(o.currency) IN ('NG') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='NGN')
--       WHEN UPPER(o.currency) IN ('TZ') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='TZS')
--       WHEN UPPER(o.currency) IN ('BY') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='BYN')
--       WHEN UPPER(o.currency) IN ('RO') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='RON')
--       WHEN UPPER(o.currency) IN ('ID') THEN (SELECT exchangerate FROM immdata.exchangerates WHERE currency='IDR')
--       ELSE (SELECT exchangerate FROM immdata.exchangerates e WHERE e.currency = UPPER(o.currency))
--     END AS fx_rate_cny
-- FROM immdata.imt_subscriptiongoodsorder o
-- WHERE COALESCE(o.isdeleted,0)=0;
