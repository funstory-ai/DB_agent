# Stripe 资源与字段目录（实测）

> 2026-11-18 用受限只读 Key（`rk_live_...`）对 `api.stripe.com/v1` 逐个 list 一条样本，取回的**真实字段键名**；仅列键名，不含客户 PII / Key。字段会随账号 API 版本（账号默认 2022-11-15，SDK 绑 2023-08-16）和 Key 权限变化，正式取数前用 `scripts/stripe_probe_20261118.py` 复核。
>
> 标记：✅ 可读 · ❌ 当前 Key 403（缺权限）· ⭐ 本项目分析常用

## 权限矩阵（14 可读 / 3 不可读）

| 资源 | 状态 | 本项目用途 |
|------|------|-----------|
| `/customers` | ✅ | ⭐ email → userid；`expand[]` 带出 |
| `/invoices` | ✅ | ⭐⭐ 收入主对象、取消桥接 |
| `/subscriptions` | ✅ | ⭐⭐ 订阅状态、取消原因、套餐 |
| `/charges` | ✅ | ⭐ 扣款失败原因、退款链 |
| `/payment_intents` | ✅ | ⭐ invoice→charge 桥 |
| `/refunds` | ✅ | ⭐ 退款漏损 |
| `/disputes` | ✅ | ⭐ 争议 |
| `/prices` | ✅ | ⭐ 套餐档位 |
| `/products` | ✅ | 产品名 |
| `/balance_transactions` | ✅ | 净额/手续费 |
| `/payouts` | ✅ | 结算 |
| `/coupons` | ✅ | 优惠 |
| `/events` | ✅ | 事件流（可选） |
| `/credit_notes` | ✅ | 冲销/退款凭证（实测可读） |
| `/checkout/sessions` | ❌ 403 `more_permissions_required` | 缺 `checkout_session_read`；需管理员补权限 |
| `/account` | ❌ 403 | 缺 `connected_account_read` |
| `/accounts` | ❌ 403 | 同上 |

## ⭐ Invoices（收入主对象，87 字段）

关键字段（完整键名见下）：
- **标识/金额**：`id`(in_*), `number`, `created`(UTC 秒), `currency`, `status`(draft/open/paid/void/uncollectible), `paid`, `amount_due`, `amount_paid`(**分**), `amount_remaining`, `subtotal`, `total`, `tax`
- **关联**：`customer`(cus_*), `subscription`(sub_*), `payment_intent`(pi_*), `charge`(ch_*), `lines`(对象, `data[].description`/`data[].price.id`/`data[].amount`)
- **原因/订阅**：`billing_reason`(`subscription_create`/`subscription_cycle`/`subscription_update`/`manual`), `subscription_details`, `period_start`, `period_end`, `description`
- **可展开**：`customer`, `lines.data.customer` — `expand[]=data.customer` 可一次带出邮箱

<details><summary>全部 87 字段（点击展开）</summary>

`account_country`, `account_name`, `account_tax_ids`, `amount_due`, `amount_overpaid`, `amount_paid`, `amount_remaining`, `amount_shipping`, `application`, `application_fee_amount`, `attempt_count`, `attempted`, `auto_advance`, `automatic_tax`, `automatically_finalizes_at`, `billing_reason`, `charge`, `collection_method`, `created`, `currency`, `custom_fields`, `customer`, `customer_account`, `customer_address`, `customer_email`, `customer_name`, `customer_phone`, `customer_shipping`, `customer_tax_exempt`, `customer_tax_ids`, `default_payment_method`, `default_source`, `default_tax_rates`, `description`, `discount`, `discounts`, `due_date`, `effective_at`, `ending_balance`, `footer`, `from_invoice`, `hosted_invoice_url`, `invoice_pdf`, `issuer`, `last_finalization_error`, `latest_revision`, `lines`, `livemode`, `metadata`, `next_payment_attempt`, `number`, `object`, `on_behalf_of`, `paid`, `paid_out_of_band`, `parent`, `payment_intent`, `payment_settings`, `period_end`, `period_start`, `post_payment_credit_notes_amount`, `pre_payment_credit_notes_amount`, `quote`, `receipt_number`, `rendering`, `rendering_options`, `shipping_cost`, `shipping_details`, `starting_balance`, `statement_descriptor`, `status`, `status_transitions`, `subscription`, `subscription_details`, `subtotal`, `subtotal_excluding_tax`, `tax`, `test_clock`, `total`, `total_discount_amounts`, `total_excluding_tax`, `total_pretax_credit_amounts`, `total_tax_amounts`, `total_taxes`, `transfer_data`, `webhooks_delivered_at`

</details>

## ⭐ Subscriptions（订阅/取消，50 字段）

关键字段：
- `id`(sub_*), `customer`, `status`(active/canceled/past_due/trialing...), `created`, `canceled_at`, `ended_at`, `cancel_at_period_end`
- **`cancellation_details`**：对象，含 `reason`(`cancellation_requested`/`payment_failed`/`subscription_ended`) 与 `comment`(自由文本，多语种，覆盖率低) — **流失原因核心字段**
- `items`：`data[].price.id`/`unit_amount`/`currency`/`recurring.interval`, `data[].quantity` — 判套餐档位
- `latest_invoice`, `plan`, `quantity`, `trial_start`, `trial_end`, `billing_cycle_anchor`, `current_period_start/end`, `metadata`, `discount`

<details><summary>全部 50 字段</summary>

`application`, `application_fee_percent`, `automatic_tax`, `billing_cycle_anchor`, `billing_cycle_anchor_config`, `billing_mode`, `billing_thresholds`, `cancel_at`, `cancel_at_period_end`, `canceled_at`, `cancellation_details`, `collection_method`, `created`, `currency`, `current_period_end`, `current_period_start`, `customer`, `customer_account`, `days_until_due`, `default_payment_method`, `default_source`, `description`, `discount`, `discounts`, `ended_at`, `id`, `invoice_settings`, `items`, `latest_invoice`, `livemode`, `managed_payments`, `metadata`, `next_pending_invoice_item_invoice`, `object`, `on_behalf_of`, `pause_collection`, `payment_settings`, `pending_invoice_item_interval`, `pending_setup_intent`, `pending_update`, `plan`, `quantity`, `schedule`, `start_date`, `status`, `test_clock`, `transfer_data`, `trial_end`, `trial_settings`, `trial_start`

</details>

## ⭐ Customers（23 字段）

`id`(cus_*), `email`, `name`, `description`, `created`, `currency`, `balance`, `delinquent`, `address`, `shipping`, `phone`, `preferred_locales`, `tax_exempt`, `discount`, `default_source`, `invoice_settings`, `invoice_prefix`, `next_invoice_sequence`, `customer_account`, `livemode`, `metadata`, `object`, `test_clock`

## ⭐ Charges（扣款，47 字段）

关键：`id`(ch_*), `amount`, `amount_captured`, `amount_refunded`, `currency`, `status`, `paid`, `captured`, `refunded`, `disputed`, `dispute`, `failure_code`, `failure_message`(支付失败原因), `invoice`, `payment_intent`, `customer`, `receipt_email`, `outcome`, `fraud_details`, `payment_method_details`, `billing_details`, `balance_transaction`, `metadata`, `created`

<details><summary>全部 47 字段</summary>

`amount`, `amount_captured`, `amount_refunded`, `application`, `application_fee`, `application_fee_amount`, `balance_transaction`, `billing_details`, `calculated_statement_descriptor`, `captured`, `created`, `currency`, `customer`, `description`, `destination`, `dispute`, `disputed`, `failure_balance_transaction`, `failure_code`, `failure_message`, `fraud_details`, `id`, `invoice`, `livemode`, `metadata`, `object`, `on_behalf_of`, `order`, `outcome`, `paid`, `payment_intent`, `payment_method`, `payment_method_details`, `radar_options`, `receipt_email`, `receipt_number`, `receipt_url`, `refunded`, `review`, `shipping`, `source`, `source_transfer`, `statement_descriptor`, `statement_descriptor_suffix`, `status`, `transfer_data`, `transfer_group`

</details>

## ⭐ Payment Intents（47 字段）

关键：`id`(pi_*), `amount`, `amount_received`, `currency`, `status`, `invoice`, `latest_charge`, `customer`, `created`, `last_payment_error`, `payment_method_types`, `canceled_at`, `cancellation_reason`, `receipt_email`, `metadata`

<details><summary>全部 47 字段</summary>

`allowed_payment_method_types`, `amount`, `amount_capturable`, `amount_details`, `amount_received`, `application`, `application_fee_amount`, `automatic_payment_methods`, `canceled_at`, `cancellation_reason`, `capture_method`, `client_secret`, `confirmation_method`, `created`, `currency`, `customer`, `customer_account`, `description`, `excluded_payment_method_types`, `id`, `invoice`, `last_payment_error`, `latest_charge`, `livemode`, `managed_payments`, `metadata`, `next_action`, `object`, `on_behalf_of`, `payment_details`, `payment_method`, `payment_method_configuration_details`, `payment_method_options`, `payment_method_types`, `payment_record`, `processing`, `receipt_email`, `review`, `setup_future_usage`, `shared_payment_granted_token`, `shipping`, `source`, `statement_descriptor`, `statement_descriptor_suffix`, `status`, `transfer_data`, `transfer_group`

</details>

## ⭐ Refunds（20 字段）

`id`, `amount`(分), `currency`, `status`(succeeded/pending/failed/canceled), `reason`, `payment_intent`, `charge`, `customer`, `created`, `balance_transaction`, `metadata`, `receipt_number`, `destination_details`, `presentment_details`, `object`, `application`, `customer_account`, `payment_method`, `source_transfer_reversal`, `transfer_reversal`

## ⭐ Disputes（19 字段）

`id`, `amount`, `currency`, `status`(needs_response/won/lost/...), `reason`, `payment_intent`, `charge`, `created`, `balance_transaction`, `balance_transactions`, `evidence`, `evidence_details`, `is_charge_refundable`, `payment_method_details`, `metadata`, `object`, `livemode`, `enhanced_eligibility_types`, `intended_submission_method`

## ⭐ Prices（19 字段，判套餐档位）

`id`(price_*), `product`, `unit_amount`(分), `unit_amount_decimal`, `currency`, `active`, `type`, `recurring`(对象, `interval`=month/year), `billing_scheme`, `tiers_mode`, `lookup_key`, `nickname`, `tax_behavior`, `transform_quantity`, `custom_unit_amount`, `created`, `livemode`, `metadata`, `object`

## Products（22 字段）

`id`, `name`, `description`, `active`, `type`, `default_price`, `attributes`, `features`, `marketing_features`, `images`, `url`, `unit_label`, `statement_descriptor`, `tax_code`, `tax_details`, `package_dimensions`, `shippable`, `created`, `updated`, `livemode`, `metadata`, `object`

## Balance Transactions（16 字段）

`id`, `amount`, `net`, `fee`, `fee_details`(手续费明细), `currency`, `created`, `available_on`, `status`, `type`, `reporting_category`, `description`, `source`, `exchange_rate`, `balance_type`, `object`

## Payouts（27 字段）

`id`, `amount`, `currency`, `status`, `arrival_date`, `created`, `automatic`, `type`, `method`, `destination`, `balance_transaction`, `description`, `failure_code`, `failure_message`, `application_fee`, `application_fee_amount`, `metadata`, `original_payout`, `reversed_by`, `payout_method`, `reconciliation_status`, `source_type`, `statement_descriptor`, `trace_id`, `livemode`, `application`, `object`

## Coupons（16 字段）

`id`, `name`, `duration`, `duration_in_months`, `amount_off`, `percent_off`, `currency`, `max_redemptions`, `times_redeemed`, `redeem_by`, `valid`, `created`, `metadata`, `object`, `livemode`, `type`

## Events（9 字段）

`id`, `type`(如 `customer.subscription.deleted`), `created`, `data`(对象), `api_version`, `livemode`, `object`, `pending_webhooks`, `request`

## Credit Notes（36 字段，冲销凭证）

关键：`id`, `reason`, `amount`, `currency`, `status`, `invoice`, `customer`, `refund`, `refunds`, `memo`, `total`, `subtotal`, `type`, `created`, `voided_at`, `lines`

<details><summary>全部 36 字段</summary>

`amount`, `amount_shipping`, `created`, `currency`, `customer`, `customer_account`, `customer_balance_transaction`, `discount_amount`, `discount_amounts`, `effective_at`, `id`, `invoice`, `lines`, `livemode`, `memo`, `metadata`, `number`, `object`, `out_of_band_amount`, `pdf`, `post_payment_amount`, `pre_payment_amount`, `pretax_credit_amounts`, `reason`, `refund`, `refunds`, `shipping_cost`, `status`, `subtotal`, `subtotal_excluding_tax`, `tax_amounts`, `total`, `total_excluding_tax`, `total_taxes`, `type`, `voided_at`

</details>

## ❌ Checkout Sessions（当前 Key 读不到）

需要 `checkout_session_read` 权限；403 响应带授权直达链接。好消息是**核心链路不需要它**：Invoice 自带 `payment_intent`，退款/争议走 `invoice → payment_intent → charge → refund/dispute` 即可（T124 修正了早期"要从 session 反取"的错误判断）。

## 常见取值形态

| 字段 | 形态 | 注意 |
|------|------|------|
| `amount_paid` / `amount` / `unit_amount` | int，**分** | 除以 100 才是主单位；日元等零小数币种除外 |
| `created` / `canceled_at` | int，Unix 秒（UTC） | 转北京日 = `date_add(hour,8,to_timestamp(created))` 或 Python `datetime.fromtimestamp(ts, tz=+8)` |
| `status=paid` + `amount_paid=0` | 试用开通 | 不是脏数据，不算收入 |
| `lines` / `items` / `cancellation_details` | 对象 | 需从 `data[].xxx` 取；list 时可 `expand[]=data.customer` 展开 |
| `billing_reason` | 枚举 | `subscription_create`(新订/试用)、`subscription_cycle`(续费)、`subscription_update`(改档) |
