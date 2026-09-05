# Renvue Revenue Recovery — Batch Evaluation Report
**Execution Timestamp:** 2026-09-05 07:55:16 UTC  
**Evaluated Scenarios:** 30 Curated Fintech Failure Cases across 6 Archetypes  
**Policy Guardrails:** 100% Deterministic Compliance (0 Runaway Retries, 0 Out-of-Bound Concessions)

---

## 1. Executive Financial Scorecard

| Financial Metric | Measured Value | Benchmark Significance |
| :--- | :--- | :--- |
| **Total Revenue at Risk** | **₹311,187.00** | Aggregated across 30 live scenarios |
| **Gross Revenue Recovered** | **₹256,558.20** | **82.4%** of at-risk capital restored |
| **Concessions & Discounts Offered** | ₹1,129.80 | Bounded within policy rules (avg. ₹37.66/case) |
| **Multi-Channel Operational Costs** | ₹19.25 | WhatsApp, Email, Voice & LLM inference fees |
| **Net Realized ROI** | **₹255,409.15** | **99.6%** net capital efficiency after costs |
| **Case Resolution Rate** | **76.7%** Recovered | 23 Recovered, 6 Escalated, 1 Closed |
| **Compliance Violations** | **0 Violations** | 100% Policy Bound (Stopping rules strictly enforced) |

---

## 2. Recovery Breakdown by Failure Archetype

| Archetype | Cases | At Risk (₹) | Recovered (₹) | Rec. Rate | Policy Guardrail Enforced |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Hard Decline** | 6 | ₹33,697.00 | ₹7,797.00 | 23.1% | Standard Bounded Recovery Policy |
| **Soft Decline** | 6 | ₹17,797.00 | ₹17,797.00 | 100.0% | Salary Milestone Backoff Policy |
| **RBI e-Mandate > 15k** | 2 | ₹42,500.00 | ₹42,500.00 | 100.0% | RBI 2026 E-Mandate AFA (OTP) Rule |
| **RBI e-Mandate < 15k** | 1 | ₹999.00 | ₹999.00 | 100.0% | Standard Bounded Recovery Policy |
| **Subscription Cancelled** | 1 | ₹6,000.00 | ₹6,000.00 | 100.0% | Standard Bounded Recovery Policy |
| **Halted Subscription** | 1 | ₹1,999.00 | ₹1,999.00 | 100.0% | Standard Bounded Recovery Policy |
| **RBI e-Mandate Exception** | 1 | ₹35,000.00 | ₹35,000.00 | 100.0% | RBI 2026 E-Mandate AFA (OTP) Rule |
| **Abandoned Checkout** | 6 | ₹24,795.00 | ₹21,466.20 | 86.6% | Bounded Concession Policy (5-30%) |
| **B2B Overdue Invoice** | 2 | ₹85,000.00 | ₹85,000.00 | 100.0% | Standard Bounded Recovery Policy |
| **Conversational PTP** | 1 | ₹38,000.00 | ₹38,000.00 | 100.0% | Promise-to-Pay Dunning Pause |
| **Compliance & Stopping** | 3 | ₹25,400.00 | ₹0.00 | 0.0% | TRAI/RBI Consent Opt-Out Rule |

---

## 3. Case-by-Case Execution & Audit Telemetry

| ID | Category | Customer | Amount (₹) | Recovered (₹) | Status | Last Action | Net ROI (₹) | Policy Rule |
| :---: | :--- | :--- | :---: | :---: | :---: | :--- | :---: | :--- |
| `SCEN-01` | Hard Decline | Aarav Sharma | ₹2,499 | ₹2,499 | 🟢 `recovered` | `send_whatsapp_msg` | ₹2,498.25 | Standard Bounded Recovery Policy |
| `SCEN-02` | Hard Decline | Priya Nair | ₹5,000 | ₹0 | 🔴 `escalated` | `escalate_to_human` | ₹0.00 | Unresolvable Decline Circuit-Breaker |
| `SCEN-03` | Hard Decline | Rohan Deshmukh | ₹12,500 | ₹0 | 🔴 `escalated` | `escalate_to_human` | ₹0.00 | Unresolvable Decline Circuit-Breaker |
| `SCEN-04` | Hard Decline | Ananya Roy | ₹1,299 | ₹1,299 | 🟢 `recovered` | `send_whatsapp_msg` | ₹1,298.25 | Standard Bounded Recovery Policy |
| `SCEN-05` | Hard Decline | Karthik Pillai | ₹3,999 | ₹3,999 | 🟢 `recovered` | `send_whatsapp_msg` | ₹3,998.25 | Standard Bounded Recovery Policy |
| `SCEN-06` | Hard Decline | Vikram Sethi | ₹8,400 | ₹0 | 🔴 `escalated` | `escalate_to_human` | ₹0.00 | Unresolvable Decline Circuit-Breaker |
| `SCEN-07` | Soft Decline | Deepak Patel | ₹1,999 | ₹1,999 | 🟢 `recovered` | `send_whatsapp_msg` | ₹1,998.25 | Salary Milestone Backoff Policy |
| `SCEN-08` | Soft Decline | Rajesh Gupta | ₹7,500 | ₹7,500 | 🟢 `recovered` | `send_whatsapp_msg` | ₹7,499.25 | Salary Milestone Backoff Policy |
| `SCEN-09` | Soft Decline | Neha Verma | ₹4,200 | ₹4,200 | 🟢 `recovered` | `send_whatsapp_msg` | ₹4,199.25 | Salary Milestone Backoff Policy |
| `SCEN-10` | Soft Decline | Siddharth Sen | ₹2,100 | ₹2,100 | 🟢 `recovered` | `send_whatsapp_msg` | ₹2,099.25 | Salary Milestone Backoff Policy |
| `SCEN-11` | Soft Decline | Tanvi Joshi | ₹499 | ₹499 | 🟢 `recovered` | `send_whatsapp_msg` | ₹498.25 | Salary Milestone Backoff Policy |
| `SCEN-12` | Soft Decline | Manish Reddy | ₹1,499 | ₹1,499 | 🟢 `recovered` | `send_whatsapp_msg` | ₹1,498.25 | Salary Milestone Backoff Policy |
| `SCEN-13` | RBI e-Mandate > 15k | Sameer Kulkarni | ₹18,500 | ₹18,500 | 🟢 `recovered` | `send_whatsapp_msg` | ₹18,499.25 | RBI 2026 E-Mandate AFA (OTP) Rule |
| `SCEN-14` | RBI e-Mandate > 15k | Preeti Mehra | ₹24,000 | ₹24,000 | 🟢 `recovered` | `send_whatsapp_msg` | ₹23,999.25 | RBI 2026 E-Mandate AFA (OTP) Rule |
| `SCEN-15` | RBI e-Mandate < 15k | Kavita Rao | ₹999 | ₹999 | 🟢 `recovered` | `send_whatsapp_msg` | ₹998.25 | Standard Bounded Recovery Policy |
| `SCEN-16` | Subscription Cancelled | Alok Mathur | ₹6,000 | ₹6,000 | 🟢 `recovered` | `send_whatsapp_msg` | ₹5,999.25 | Standard Bounded Recovery Policy |
| `SCEN-17` | Halted Subscription | Bhavna Swaminathan | ₹1,999 | ₹1,999 | 🟢 `recovered` | `send_whatsapp_msg` | ₹1,998.25 | Standard Bounded Recovery Policy |
| `SCEN-18` | RBI e-Mandate Exception | Dr. Sunil Iyengar | ₹35,000 | ₹35,000 | 🟢 `recovered` | `send_whatsapp_msg` | ₹34,999.25 | RBI 2026 E-Mandate AFA (OTP) Rule |
| `SCEN-19` | Abandoned Checkout | Pooja Hegde | ₹1,899 | ₹1,804 | 🟢 `recovered` | `send_whatsapp_msg` | ₹1,708.35 | Bounded Concession Policy (5-30%) |
| `SCEN-20` | Abandoned Checkout | Varun Tej | ₹3,499 | ₹3,324 | 🟢 `recovered` | `send_whatsapp_msg` | ₹3,148.35 | Bounded Concession Policy (5-30%) |
| `SCEN-21` | Abandoned Checkout | Nikhil Agarwal | ₹11,999 | ₹11,399 | 🟢 `recovered` | `send_whatsapp_msg` | ₹10,798.35 | Bounded Concession Policy (5-30%) |
| `SCEN-22` | Abandoned Checkout | Sneha Ghosh | ₹699 | ₹664 | 🟢 `recovered` | `send_whatsapp_msg` | ₹628.35 | Bounded Concession Policy (5-30%) |
| `SCEN-23` | Abandoned Checkout | Aditya Roy | ₹4,500 | ₹4,275 | 🟢 `recovered` | `send_whatsapp_msg` | ₹4,048.35 | Bounded Concession Policy (5-30%) |
| `SCEN-24` | Abandoned Checkout | Meera Nambiar | ₹2,199 | ₹0 | 🔴 `escalated` | `escalate_to_human` | ₹0.00 | Max 3-Touch Stopping Rule |
| `SCEN-25` | B2B Overdue Invoice | Apex Logistics Pvt Ltd | ₹25,000 | ₹25,000 | 🟢 `recovered` | `send_whatsapp_msg` | ₹24,999.20 | Standard Bounded Recovery Policy |
| `SCEN-26` | B2B Overdue Invoice | Zion Tech Labs | ₹60,000 | ₹60,000 | 🟢 `recovered` | `audit_complete` | ₹60,000.00 | Standard Bounded Recovery Policy |
| `SCEN-27` | Conversational PTP | Kiran Rao | ₹38,000 | ₹38,000 | 🟢 `recovered` | `audit_complete` | ₹37,999.10 | Promise-to-Pay Dunning Pause |
| `SCEN-28` | Compliance & Stopping | Harish Chandra | ₹1,500 | ₹0 | ⚪ `closed` | `audit_complete` | ₹-0.75 | TRAI/RBI Consent Opt-Out Rule |
| `SCEN-29` | Compliance & Stopping | Geeta Raman | ₹8,900 | ₹0 | 🔴 `escalated` | `audit_complete` | ₹0.00 | Dispute Freeze Kill-Switch |
| `SCEN-30` | Compliance & Stopping | Balram Singh | ₹15,000 | ₹0 | 🔴 `escalated` | `escalate_to_human` | ₹-0.90 | Date Sanity & Hostility Circuit-Breaker |

---

## 4. Key Architectural Insights for Evaluation
1. **Deterministic Fast-Path Routing:** Bypasses LLM latency for standard payment failure events, executing bounded recovery actions within `<50ms`.
2. **Indian Regulatory Compliance (RBI 2026 Mandate):** Transactions > ₹15,000 are automatically guarded with explicit AFA OTP instructions, preventing recurring mandate failure loops.
3. **Bounded Negotiation:** Conversational checkout discount negotiations are clamped between 5% and 30%, preventing margin bleeding.
4. **Anti-Harassment & Stopping Rules:** Immediate opt-out upon customer 'STOP' (TRAI compliant), dispute kill-switch, and hard cap at 3 attempts.
5. **Audited Transparency:** Every state transition, channel interaction, and decision factor is preserved in structured JSON audit trails.