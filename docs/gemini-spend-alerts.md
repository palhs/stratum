# Gemini API Spend Alerts — Configuration Guide

## 1. Overview

**Purpose:** Prevent unexpected Gemini API costs during v2.0 batch report generation.

**Two-layer defense:**

| Layer | Mechanism | Behavior |
|-------|-----------|----------|
| Layer 1 | Cloud Billing budget alerts | Tiered email notifications at 50%, 80%, 100% of budget — requires key linked to a Cloud project |
| Layer 2 | AI Studio monthly spend cap | Hard stop with ~10 min billing data lag — available for all AI Studio keys |

**Expected usage pattern:** A 20-stock batch run generates approximately 120 Gemini API calls per run (6 LangGraph nodes × 20 stocks). At gemini-2.0-flash-001 pricing, a single batch run costs on the order of $0.05–$0.50 depending on output token volume. A conservative monthly budget of $20 provides room for ~40–400 batch runs per month.

---

## 2. Determine Your Billing Path

Before configuring alerts, determine which billing path applies to your `GEMINI_API_KEY`:

1. Go to **AI Studio** (aistudio.google.com) → Settings (gear icon) → **Billing**
2. Check whether the key is linked to a Google Cloud project with a billing account
   - If the Settings → Billing page shows a Cloud project name and billing account → **follow Section 3a (Cloud Billing path)**
   - If the page shows "No billing account" or only shows a spend cap option with no Cloud project → **follow Section 3b (AI Studio-only path)**

This is a prerequisite decision: the two paths use different mechanisms and the correct choice determines whether tiered threshold alerts are available.

---

## 3a. Cloud Billing Budget Setup (Recommended Path)

Use this path when your Gemini API key is linked to a Google Cloud project with an active billing account. This is the recommended configuration because it provides tiered email notifications.

### Steps

1. Navigate to **Google Cloud Console** → **Billing** → **Budgets & alerts**
   - Direct link: `console.cloud.google.com/billing` → select your billing account → Budgets & alerts

2. Click **"Create Budget"**

3. **Scope:**
   - Budget type: Cost budget
   - Projects: select the Cloud project linked to your Gemini API key
   - Services: leave as "All services" (or filter to "Cloud AI" if you want Gemini-only tracking)
   - Click **Next**

4. **Budget amount:**
   - Budget type: Specified amount
   - Amount: `$20` per month (conservative starting point for a single-user system running occasional batch reports)
   - Note: Adjust this amount after your first batch run when you have actual cost data

5. **Alert threshold rules — add three rules:**

   | Rule | % of Budget | Type | Alert at |
   |------|-------------|------|----------|
   | Early warning | 50% | Actual spend | $10 |
   | Action needed | 80% | Actual spend | $16 |
   | Budget reached | 100% | Actual spend | $20 |

   To add each rule: click **"Add threshold rule"**, set percentage, select "Actual" (not forecasted), click **"Done"**.

6. **Notification — email alerts:**
   - Check **"Email alerts to billing admins and users"**
   - This sends email to all users on the billing account with the Billing Administrator or Billing Account User role

7. **Optional — custom notification channel:**
   - Click **"Connect a Pub/Sub topic"** or **"Manage notification channels"** in Cloud Monitoring
   - Add a custom email channel to receive alerts at a specific address not on the billing account
   - This is optional and useful if the billing account admin email is not monitored

8. Click **"Finish"** to create the budget

### Verification

After creation, the budget appears in the Budgets & alerts list. Each threshold rule has a **"Test notification"** button — click it to fire a test email to the configured notification channel. Confirm the email arrives with the expected subject line (typically "Budget alert: [budget name] has reached [threshold]%").

---

## 3b. AI Studio-Only Path (Limited)

Use this path only if your Gemini API key is provisioned via AI Studio without a linked Google Cloud project. This path provides a hard spend cap but **does not provide tiered email notifications**.

### Steps

1. Go to **AI Studio** (aistudio.google.com) → click your profile → **Billing** or navigate to the **Spend** page
2. Locate the **Monthly spend cap** section
3. Set the cap amount (e.g., `$20/month`)
4. Save the configuration

### Known Limitation

The AI Studio spend cap is a **hard stop** mechanism, not a notification system. When your spend reaches the cap, API calls begin returning errors. There are no warning thresholds — the cap fires at 100% of the set amount, with approximately a 10-minute billing data lag before enforcement.

**If you are on this path, tiered alerts (50%, 80%) are not available.** The only mitigation is to set the cap conservatively (e.g., $15 instead of $20) to leave headroom before batch runs are disrupted.

Document this as a known limitation in your Configuration Record (Section 6).

---

## 4. AI Studio Spend Cap (Both Paths)

Regardless of which billing path you used in Section 3, configure the AI Studio spend cap as a safety backstop. It acts as a final circuit-breaker even if email alerts are missed.

1. Go to **AI Studio** → **Spend** page (aistudio.google.com → your project → Spend)
2. Set the **Monthly spend cap** to your chosen amount (e.g., `$20/month`)
3. Save

**Note:** This feature is marked "experimental" by Google. Its enforcement behavior may change. Check that it remains active after major AI Studio updates.

If you are on the Cloud Billing path (Section 3a), the spend cap provides a second layer of protection after budget alerts fire. Set it at or slightly above your Cloud Billing budget amount so the hard stop aligns with your alerting tier.

---

## 5. Testing Alerts

### Cloud Billing Path

1. Navigate to Google Cloud Console → Billing → Budgets & alerts → your budget
2. Click into the budget detail view
3. Each threshold rule (50%, 80%, 100%) has a **"Test notification"** button
4. Click **"Test notification"** on the 100% rule
5. Within a few minutes, the configured email address should receive a test alert email
6. Expected sender: `noreply@cloudidentity.google.com` or similar Google billing sender
7. Expected subject: `Budget Alert: [your budget name] has exceeded 100% of your [amount] budget`

This is the correct mechanism for verifying alert delivery per the SRVC-07 success criterion. No actual spend is required.

### AI Studio Spend Cap Path

There is no test mechanism for the AI Studio spend cap. Verification is observational:

1. After a small batch run (2–3 stocks), navigate to AI Studio → Spend page
2. Confirm the spend counter has updated (within ~10 minutes of the run completing)
3. Confirm the cap value is still set to your configured amount

---

## 6. Configuration Record

Fill in this template after completing the setup above. Commit the filled-in version to the repository as the authoritative record.

```
Billing path:         AI Studio Only
Cloud project name:   My First Project
Monthly budget:       $200
Threshold tiers:      N/A
Notification email:   phananhle2003@gmail.com
AI Studio spend cap:  $200
Date configured:      2026-03-17
Test notification:    Not tested
```

**Example (Cloud Billing path):**
```
Billing path:         Cloud Project
Cloud project name:   stratum-prod
Monthly budget:       $20
Threshold tiers:      50% ($10), 80% ($16), 100% ($20)
Notification email:   billing-admin@example.com
AI Studio spend cap:  $20
Date configured:      2026-03-17
Test notification:    Passed
```

**Example (AI Studio only):**
```
Billing path:         AI Studio Only
Cloud project name:   N/A
Monthly budget:       N/A — no Cloud Billing budget available
Threshold tiers:      N/A — tiered alerts not available on this path
Notification email:   N/A
AI Studio spend cap:  $15 (set conservatively — only mechanism available)
Date configured:      2026-03-17
Test notification:    N/A — no test mechanism for AI Studio spend cap
```

---

## 7. Maintenance

**Monthly review (first 3 months):**
- After each batch run, check actual spend in Cloud Billing or AI Studio
- Compare to budget amount; if a single batch run consistently costs more than $1, recalibrate the budget upward
- Watch for emails hitting the 50% threshold more than once per month — signals the budget needs adjustment

**Quarterly check:**
- Confirm Cloud Billing budget is still active (budgets can be accidentally deleted)
- Verify notification email is still monitored
- Check AI Studio spend cap is still set (experimental feature — verify it hasn't been reset)

**When batch workload scales:**
- If moving from 20-stock to 50-stock batches, expected API call volume increases proportionally (from 120 to 300 calls per run)
- Update budget amount before running larger batches — do not rely on the 100% alert as the first signal

**Model change impact:**
- If gemini-2.0-flash-001 is replaced by a higher-cost model, recalibrate the budget
- Cost per token varies significantly across Gemini model versions
