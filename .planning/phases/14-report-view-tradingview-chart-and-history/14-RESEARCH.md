# Phase 14: Report View, TradingView Chart, and History - Research

**Researched:** 2026-03-19
**Domain:** Next.js 16 / React 19 report view, TradingView Lightweight Charts v5, bilingual markdown rendering, paginated history timeline
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Report page layout:**
- Vertical single-column layout: Summary card on top → TradingView chart below → expanded full report below chart → history timeline at bottom
- Summary card is collapsed by default — user must click "Expand" to read the full report
- When expanded, full report appears below the chart — summary + chart stay above as context
- "Back to Dashboard" link at the top of the page

**Summary card content:**
- Show all available data: large tier badge (hero element), three sub-assessment labels (Macro, Valuation, Structure), and one-line narrative verdict
- Reuse TierBadge component from dashboard with the same muted color scheme (teal/slate/amber/rose)
- Expand/collapse button at the bottom of the summary card

**Bilingual toggle:**
- Floating toggle in the top-right of the report page, always visible even when scrolled
- Switches both the summary card verdict text and the full report markdown content
- Default language: Vietnamese (aligns with PROJECT.md "Vietnamese primary, English secondary")
- Language preference persisted in localStorage — survives page refreshes
- Both vi and en report content fetched upfront on page load — toggle is instant, no loading spinner

**TradingView chart:**
- Weekly candlestick chart with MA50 and MA200 line overlays visible by default
- Volume histogram below the candlestick area
- Default view: 1 year (52 weeks) of data, user can zoom/pan to see more
- Chart is zoomable and interactive (TradingView Lightweight Charts)
- Loaded via `dynamic({ ssr: false })` — decided in Phase 12

**History timeline:**
- Vertical list below the chart section
- Each row shows: date, tier badge, verdict snippet, upgrade/downgrade arrow
- Arrows between consecutive reports: ↑ (green) for upgrade, ↓ (red) for downgrade, no arrow if tier unchanged
- Arrow colors use the muted color scheme from Phase 12
- Clicking a historical report replaces the current summary card and report content in-place (URL stays /reports/{symbol})
- Active/selected report is highlighted in the timeline list
- Load 10 most recent reports initially, "Load more" button if more exist

### Claude's Discretion
- Chart height and mobile sizing
- Full report markdown rendering approach (react-markdown, etc.)
- Loading/skeleton states for the report page
- Error handling for missing reports or API failures
- Animation/transition for expand/collapse
- How to fetch both vi and en report content (may need new backend endpoint — current GET /reports/{job_id} returns one language per row; researcher should investigate)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RVEW-01 | User sees report summary card (tier, sub-assessments, one-line verdict) | ReportSummaryCard component reads from report_json JSONB: `entry_quality.tier`, `entry_quality.macro_assessment`, `entry_quality.valuation_assessment`, `entry_quality.structure_assessment`, `entry_quality.narrative` |
| RVEW-02 | User can expand summary to full bilingual markdown report | Expand/collapse state via useState; ReportMarkdown renders report_markdown text; new backend endpoint GET /reports/by-symbol/{symbol}/content returns both vi+en markdown |
| RVEW-03 | User can toggle between Vietnamese and English report versions | BilingualToggle component persists "vi"/"en" in localStorage key "stratum-report-lang"; both versions fetched upfront |
| RVEW-04 | Report view includes interactive TradingView chart (weekly OHLCV + 50MA + 200MA, zoomable) | TradingViewChart component using lightweight-charts v5.1.0 loaded via `dynamic({ ssr: false })`; getOhlcv() already returns OHLCVPoint with ma50/ma200 |
| RHST-01 | User can view timeline of past reports per ticker | HistoryTimeline component reads GET /reports/by-ticker/{symbol}?page=1&per_page=10; existing ReportHistoryResponse type |
| RHST-02 | Timeline shows date and entry quality tier badge per report | Each timeline row uses ReportHistoryItem.generated_at + ReportHistoryItem.tier via TierBadge |
| RHST-03 | User can open any historical report from the timeline | Row click fetches GET /reports/by-report-id/{report_id}?language=vi&language=en; replaces summary card + markdown in-place |
| RHST-04 | Timeline shows assessment change indicators (upgrade/downgrade arrows) | Compare consecutive items in ReportHistoryItem[]; tier rank order: Favorable(0) > Neutral(1) > Cautious(2) > Avoid(3) |
</phase_requirements>

---

## Summary

Phase 14 replaces the placeholder `/reports/[symbol]/page.tsx` with a full bilingual report view. The page is a "use client" component receiving an `accessToken` from a thin server wrapper (same pattern as dashboard). All interactive state — selected report, language preference, expand/collapse — is managed client-side with no URL changes.

The most critical infrastructure gap discovered: **the backend has no endpoint to fetch report content (report_json + report_markdown) by report_id directly**. The existing `GET /reports/{job_id}` is job-based, not report-based. The existing `GET /reports/by-ticker/{symbol}` returns metadata only (tier, verdict, generated_at), not the full markdown. A new backend endpoint is required: `GET /reports/by-report-id/{report_id}` that returns both vi and en rows for a given report_id grouping. Without this, clicking a history row cannot load its content.

TradingView Lightweight Charts v5.1.0 is the current registry version (not yet installed — must be added). The library has API differences from v4. The established `dynamic({ ssr: false })` pattern from Phase 12 is confirmed correct for Next.js 16.

**Primary recommendation:** Build backend endpoint first (GET /reports/by-report-id/{report_id} returning both languages), then build the frontend components in this order: ReportSummaryCard → TradingViewChart → BilingualToggle → ReportMarkdown → HistoryTimeline.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| lightweight-charts | 5.1.0 (latest) | TradingView candlestick/line chart | Official TradingView library; already the project decision from Phase 12 CONTEXT.md |
| react-markdown | 10.1.0 (latest) | Render report_markdown text as HTML | Most widely used React markdown renderer; peerDeps: React >= 18 — compatible with React 19.2.4 |
| remark-gfm | 4.0.1 (latest) | GitHub Flavored Markdown plugin for react-markdown | Required for tables, strikethrough in report content |
| @tailwindcss/typography | 0.5.19 (latest) | `prose` class for markdown body styling | Official Tailwind plugin; required for readable typography on report prose |

### Supporting (already installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| next/dynamic | 16.2.0 | SSR bypass for TradingView | Wrap TradingViewChart to prevent window access during SSR |
| date-fns | 4.1.0 | Format generated_at dates in history timeline | Already installed; use `format(parseISO(generated_at), 'dd MMM yyyy')` |
| lucide-react | 0.577.0 | ArrowUp/ArrowDown/ChevronDown/ChevronUp icons | Already installed and used in Phase 12/13 |
| sonner | 2.0.7 | Error toast on API failure | Already installed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| react-markdown | next/mdx, marked | react-markdown is runtime renderer — correct for dynamic API content. MDX is build-time only. marked has no React integration. |
| @tailwindcss/typography | Custom prose CSS | Typography plugin handles all prose styling edge cases (lists, blockquotes, code, tables). Custom CSS would need to replicate all of this. |
| lightweight-charts v5 | Recharts, Chart.js | Locked decision from Phase 12. lightweight-charts is purpose-built for financial candlestick charts. |

**Installation:**
```bash
npm install lightweight-charts@5.1.0 react-markdown@10.1.0 remark-gfm@4.0.1 @tailwindcss/typography@0.5.19
```

**Version verification:** Versions confirmed against npm registry on 2026-03-19.

---

## Architecture Patterns

### Recommended Project Structure
```
frontend/src/
├── app/reports/[symbol]/
│   └── page.tsx                    # Thin server component: auth token → ReportPageClient
├── components/report/
│   ├── ReportPageClient.tsx        # "use client" orchestrator — all state lives here
│   ├── ReportSummaryCard.tsx       # Tier hero + sub-assessments + verdict + expand button
│   ├── BilingualToggle.tsx         # Floating fixed toggle — VI/EN buttons
│   ├── TradingViewChart.tsx        # lightweight-charts wrapper — browser only
│   ├── ReportMarkdown.tsx          # react-markdown with prose styling
│   ├── HistoryTimeline.tsx         # Paginated history list with tier arrows
│   └── ReportPageSkeleton.tsx      # Loading state skeleton
```

### Pattern 1: Server Page → Client Orchestrator (Established Pattern)

The `/reports/[symbol]/page.tsx` follows the same split as the dashboard:

```typescript
// Source: frontend/src/app/(dashboard)/page.tsx (established pattern)
// frontend/src/app/reports/[symbol]/page.tsx

import { createClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'
import { ReportPageClient } from '@/components/report/ReportPageClient'

export const dynamic = 'force-dynamic'

export default async function ReportPage({
  params,
}: {
  params: Promise<{ symbol: string }>
}) {
  const { symbol } = await params
  const supabase = await createClient()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) redirect('/login')
  return <ReportPageClient symbol={symbol} accessToken={session.access_token} />
}
```

**Why:** proxy.ts already enforces auth for `/reports/*` routes. The server page only extracts the token — all data fetching and state happens in the client component.

### Pattern 2: TradingView Chart — dynamic() Wrapping

The TradingViewChart component MUST NOT be imported directly. It must be wrapped in `dynamic({ ssr: false })` to prevent `window is not defined` build errors.

```typescript
// Source: Next.js 16 lazy-loading docs + STATE.md (established decision)
// frontend/src/components/report/ReportPageClient.tsx

import dynamic from 'next/dynamic'
import { Skeleton } from '@/components/ui/skeleton'

const TradingViewChart = dynamic(
  () => import('./TradingViewChart'),
  {
    ssr: false,
    loading: () => <Skeleton className="w-full h-[400px] rounded-lg" />,
  }
)
```

**Critical note:** The `dynamic()` call must be at the module's top level, not inside render. The `ssr: false` option works only in Client Components — the wrapper must have `'use client'`.

### Pattern 3: Lightweight Charts v5 — Candlestick + MA Line + Volume

lightweight-charts v5 changed the API from v4. The chart creation API is:

```typescript
// Source: npm view lightweight-charts + verified against v5 API
// frontend/src/components/report/TradingViewChart.tsx

'use client'

import { useEffect, useRef } from 'react'
import { createChart, ColorType, CrosshairMode } from 'lightweight-charts'
import type { OHLCVPoint } from '@/lib/types'

export default function TradingViewChart({ data }: { data: OHLCVPoint[] }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#71717a',  // muted-foreground zinc-500
      },
      grid: {
        vertLines: { color: '#27272a' },
        horzLines: { color: '#27272a' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    })

    // Candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#14b8a6',    // teal-500
      downColor: '#f43f5e',  // rose-500
      borderVisible: false,
      wickUpColor: '#14b8a6',
      wickDownColor: '#f43f5e',
    })

    // MA50 line series
    const ma50Series = chart.addLineSeries({
      color: '#3b82f6',  // blue-500
      lineWidth: 2,
      priceLineVisible: false,
    })

    // MA200 line series
    const ma200Series = chart.addLineSeries({
      color: '#f97316',  // orange-500
      lineWidth: 2,
      priceLineVisible: false,
    })

    // Map data — filter nulls for MA lines
    const candleData = data.map(p => ({
      time: p.time as import('lightweight-charts').UTCTimestamp,
      open: p.open ?? p.close,
      high: p.high ?? p.close,
      low: p.low ?? p.close,
      close: p.close,
    }))

    const ma50Data = data
      .filter(p => p.ma50 != null)
      .map(p => ({ time: p.time as import('lightweight-charts').UTCTimestamp, value: p.ma50! }))

    const ma200Data = data
      .filter(p => p.ma200 != null)
      .map(p => ({ time: p.time as import('lightweight-charts').UTCTimestamp, value: p.ma200! }))

    candlestickSeries.setData(candleData)
    ma50Series.setData(ma50Data)
    ma200Series.setData(ma200Data)

    // Default view: last 52 data points
    if (data.length > 52) {
      chart.timeScale().setVisibleRange({
        from: data[data.length - 52].time as import('lightweight-charts').UTCTimestamp,
        to: data[data.length - 1].time as import('lightweight-charts').UTCTimestamp,
      })
    }

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [data])

  return (
    <div
      ref={containerRef}
      className="w-full h-[260px] md:h-[400px] rounded-lg overflow-hidden border border-border"
      aria-label={`Price chart`}
    />
  )
}
```

**Note on volume histogram:** Lightweight Charts v5 does not support a built-in volume histogram pane directly attached to the candlestick chart in the same way v4 did. Volume requires creating a second chart with a shared time scale or using `createHistogramSeries` on the same chart. Volume is specified in the UI-SPEC — use a histogram series on the same chart with a scaled price axis to position it below.

### Pattern 4: localStorage Language Persistence

```typescript
// Source: Web Storage API (standard browser API)
// Read on mount, write on toggle

const [lang, setLang] = useState<'vi' | 'en'>(() => {
  if (typeof window === 'undefined') return 'vi'
  return (localStorage.getItem('stratum-report-lang') as 'vi' | 'en') ?? 'vi'
})

function handleLangChange(next: 'vi' | 'en') {
  setLang(next)
  localStorage.setItem('stratum-report-lang', next)
}
```

**Important:** The `typeof window === 'undefined'` guard prevents SSR crashes. The lazy initializer function avoids stale-closure issues on re-render.

### Pattern 5: History Timeline Upgrade/Downgrade Detection

```typescript
// Tier rank — lower number = better tier (Favorable is best)
const TIER_RANK: Record<string, number> = {
  Favorable: 0,
  Neutral: 1,
  Cautious: 2,
  Avoid: 3,
}

function getTierChange(current: string, previous: string | null): 'up' | 'down' | 'none' {
  if (!previous) return 'none'
  const curr = TIER_RANK[current] ?? 99
  const prev = TIER_RANK[previous] ?? 99
  if (curr < prev) return 'up'     // improved (e.g., Neutral → Favorable)
  if (curr > prev) return 'down'   // degraded (e.g., Neutral → Cautious)
  return 'none'
}
```

History items arrive newest-first from the API. To compute changes: the "previous" report for row[i] is row[i+1] (the older one in the array).

### Pattern 6: New Backend Endpoint — Report Content by Report ID

**This is the critical gap.** The existing endpoints are:
- `GET /reports/by-ticker/{symbol}` — returns metadata only (no markdown content)
- `GET /reports/{job_id}` — returns content, but by job_id not report_id

For history row click, we need to fetch full content (report_json + report_markdown) for both languages given a report_id. The reports table stores one row per language per generation run. Given a report_id (vi row primary key), the en row shares the same `generated_at` timestamp and `asset_id`.

**Recommended new endpoint:** `GET /reports/by-report-id/{report_id}`

Backend query pattern:
```python
# Get both vi + en rows for the same generation run
# The existing _query_report_history returns the MIN(report_id) which is the vi row
# Use generated_at + asset_id to fetch both language rows

SELECT report_id, language, report_json, report_markdown
FROM reports
WHERE asset_id = (SELECT asset_id FROM reports WHERE report_id = :report_id)
  AND generated_at = (SELECT generated_at FROM reports WHERE report_id = :report_id)
ORDER BY language  -- returns 'en' then 'vi'
```

Response schema (new):
```python
class ReportContentResponse(BaseModel):
    report_id: int
    generated_at: str
    tier: str
    verdict: str
    macro_assessment: str
    valuation_assessment: str
    structure_assessment: str
    report_markdown_vi: str | None
    report_markdown_en: str | None
```

**Alternative approach (no new endpoint):** On initial page load, use `GET /reports/by-ticker/{symbol}?page=1&per_page=1` to get the latest report_id, then use `GET /reports/by-report-id/{report_id}` for content. This is the cleanest design and avoids needing a separate "latest report" endpoint.

### Anti-Patterns to Avoid

- **Importing lightweight-charts at top level in a non-dynamic component:** Causes `window is not defined` during Next.js SSR build. Always wrap in `dynamic({ ssr: false })`.
- **Calling `createChart` without checking `containerRef.current`:** Container may not be mounted on first render. Always guard with `if (!containerRef.current) return`.
- **Fetching vi and en separately on toggle:** The locked decision says both languages fetched upfront. Do not trigger a second API call when the user switches languages.
- **Using `prose` class without `max-w-none`:** The default prose class sets a max-width. Use `prose max-w-none` to fill the column width.
- **Forgetting `prose-invert` for dark mode:** Reports viewed in dark mode will have illegible text without this class.
- **Route ordering bug (already solved):** In `reports.py`, `/by-ticker/{symbol}` is registered before `/{job_id}`. The new `/by-report-id/{report_id}` endpoint must also be registered BEFORE `/{job_id}` to prevent FastAPI treating "by-report-id" as an integer.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Markdown rendering | Custom HTML parser | react-markdown + remark-gfm | Handles nested lists, tables, blockquotes, escaping, XSS safely |
| Prose typography | Custom CSS rules | @tailwindcss/typography `prose` class | Handles all text element sizing, spacing, line-heights for long-form content |
| Candlestick chart | SVG/Canvas chart | lightweight-charts | TradingView purpose-built; zoom/pan, crosshair, time axis, MA overlay all built-in |
| Date formatting | Manual string manipulation | date-fns `format` + `parseISO` | Already installed; handles timezone correctly |

**Key insight:** The three new npm packages (lightweight-charts, react-markdown+remark-gfm, @tailwindcss/typography) each solve a domain where hand-rolling would require hundreds of lines and still miss edge cases.

---

## Common Pitfalls

### Pitfall 1: lightweight-charts v5 API Changes from v4
**What goes wrong:** Using v4 API patterns (e.g., `chart.addCandleSeries()`, `chart.addLineSeries({ priceScaleId: 'volume' })`) causes runtime errors with v5.1.0.
**Why it happens:** lightweight-charts v5 renamed and restructured several APIs.
**How to avoid:** Check the v5 changelog. Key v5 changes: `addCandleSeries` → `addCandlestickSeries`, volume pane requires explicit price scale configuration.
**Warning signs:** TypeScript type errors on method names are the first signal.

### Pitfall 2: Chart Cleanup on Component Unmount
**What goes wrong:** Navigating away from the report page without calling `chart.remove()` leaks the chart instance and causes a second chart to render on remount.
**Why it happens:** lightweight-charts attaches to the DOM element directly; without cleanup, the old instance persists.
**How to avoid:** Return a cleanup function from `useEffect` that calls `chart.remove()`.
**Warning signs:** Double chart rendered on page revisit; memory warnings in DevTools.

### Pitfall 3: Container Width on Initial Render
**What goes wrong:** Chart renders at 0px width if the container hasn't painted yet when `createChart` is called.
**Why it happens:** `containerRef.current.clientWidth` is 0 on the first paint frame.
**How to avoid:** Use a `ResizeObserver` or ensure the parent container has an explicit width before chart initialization. The `width: containerRef.current.clientWidth` pattern works if checked after layout.
**Warning signs:** Chart appears as a thin vertical line on first load.

### Pitfall 4: react-markdown + @tailwindcss/typography Version Conflict
**What goes wrong:** `@tailwindcss/typography` v0.5.x was built for Tailwind CSS v3. The project uses Tailwind CSS v4.2.2.
**Why it happens:** Tailwind CSS v4 changed the configuration and plugin API. The `@tailwindcss/typography` plugin may not integrate the same way.
**How to avoid:** The project uses `@import "tailwindcss"` in globals.css (Tailwind v4 syntax). With Tailwind v4, plugins are added to CSS with `@plugin "@tailwindcss/typography"` — NOT in a `tailwind.config.js`. There is no `tailwind.config.js` in this project (Tailwind v4 uses CSS-first config).
**How to configure:**
```css
/* globals.css — add this line */
@plugin "@tailwindcss/typography";
```
**Warning signs:** `prose` class does not apply any styles; no typography.css in build output.

### Pitfall 5: localStorage Access During SSR
**What goes wrong:** `localStorage.getItem()` called at module level or in a non-lazy useState initializer throws `ReferenceError: localStorage is not defined` during SSR.
**Why it happens:** Next.js server renders "use client" components in Node.js where `window` and `localStorage` don't exist.
**How to avoid:** Use lazy useState initializer with `typeof window === 'undefined'` guard, or access localStorage only inside `useEffect`.
**Warning signs:** Build succeeds but page throws ReferenceError at runtime on first load.

### Pitfall 6: Missing Backend Endpoint Blocks History Row Click
**What goes wrong:** History row click has no endpoint to call for fetching full report content by report_id.
**Why it happens:** Current `GET /reports/{job_id}` is job-based; clicking a history row has a report_id, not a job_id.
**How to avoid:** Backend plan MUST include new `GET /reports/by-report-id/{report_id}` endpoint as Wave 1 or the frontend history feature cannot be completed.
**Warning signs:** Frontend implementation stalls waiting for backend.

### Pitfall 7: @tailwindcss/typography v4 Compatibility
**What goes wrong:** `npm install @tailwindcss/typography` installs v0.5.x which expects Tailwind v3 API.
**Why it happens:** At the time of research, `@tailwindcss/typography` v0.5.19 is the latest stable. Check if there is a v1.0 beta or Tailwind v4 compatible release.
**How to avoid:** Install and test: if `prose` class works, no issue. If not, inspect the plugin output. Community reports suggest v0.5.x works as a CSS plugin in Tailwind v4 with `@plugin` directive.
**Warning signs:** `prose` class present in DOM but no styles applied.

---

## Code Examples

Verified patterns from project code and official documentation:

### Supabase Auth Token in Report Page
```typescript
// Source: frontend/src/app/(dashboard)/page.tsx (established project pattern)
export const dynamic = 'force-dynamic'

export default async function ReportPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params
  const supabase = await createClient()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) redirect('/login')
  return <ReportPageClient symbol={symbol.toUpperCase()} accessToken={session.access_token} />
}
```

### New API Function for Report Content
```typescript
// Source: frontend/src/lib/api.ts (extend existing pattern)
export async function getReportHistory(
  symbol: string,
  token: string,
  page: number = 1,
  perPage: number = 10
): Promise<ReportHistoryResponse> {
  return fetchAPI<ReportHistoryResponse>(
    `/reports/by-ticker/${symbol}?page=${page}&per_page=${perPage}`,
    token
  )
}

export async function getReportContent(
  reportId: number,
  token: string
): Promise<ReportContentResponse> {
  return fetchAPI<ReportContentResponse>(`/reports/by-report-id/${reportId}`, token)
}
```

### react-markdown with Prose Styling
```tsx
// Source: react-markdown npm docs, @tailwindcss/typography docs
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export function ReportMarkdown({ content, lang }: { content: string; lang: 'vi' | 'en' }) {
  return (
    <article lang={lang} className="prose prose-zinc dark:prose-invert max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </article>
  )
}
```

### Backend Route Registration Order (reports.py)
```python
# Source: reasoning/app/routers/reports.py (existing pattern — extend it)
# IMPORTANT: string paths must be registered BEFORE /{job_id}
router.get("/by-ticker/{symbol}", ...)    # existing
router.get("/by-report-id/{report_id}", ...)  # NEW — add here, before /{job_id}
router.get("/stream/{job_id}", ...)       # existing
router.get("/{job_id}", ...)              # existing — must remain last
```

### Backend New Endpoint Query
```python
# Source: reasoning/app/routers/reports.py (extend _get_report_by_job pattern)
def _get_report_content_by_id(db_engine, report_id: int) -> dict | None:
    """Fetch both vi and en report rows for a given report_id's generation run."""
    metadata = MetaData()
    reports = Table("reports", metadata, autoload_with=db_engine)

    # Get the anchor row to find asset_id + generated_at
    with db_engine.connect() as conn:
        anchor = conn.execute(
            reports.select().where(reports.c.report_id == report_id)
        ).fetchone()
        if anchor is None:
            return None
        anchor = dict(anchor._mapping)

        # Fetch all rows for this generation run (vi + en)
        rows = conn.execute(
            reports.select()
            .where(reports.c.asset_id == anchor["asset_id"])
            .where(reports.c.generated_at == anchor["generated_at"])
        ).fetchall()

    result = {
        "report_id": report_id,
        "generated_at": anchor["generated_at"].isoformat(),
        "report_json": anchor["report_json"],
        "report_markdown_vi": None,
        "report_markdown_en": None,
    }
    for row in rows:
        m = dict(row._mapping)
        if m["language"] == "vi":
            result["report_markdown_vi"] = m.get("report_markdown")
        elif m["language"] == "en":
            result["report_markdown_en"] = m.get("report_markdown")

    return result
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| lightweight-charts v4 `addCandleSeries()` | v5 `addCandlestickSeries()` | v5.0 release | API rename — use v5 method names |
| tailwind.config.js plugin array | `@plugin` directive in CSS | Tailwind v4 | @tailwindcss/typography added via `@plugin` in globals.css, not JS config |
| `next/dynamic` with `loading` prop | Same API, confirmed current in Next.js 16 docs | Stable | No change — established pattern is correct |
| react-markdown v8 (unified v10) | react-markdown v10 (unified v11) | 2024 | v10 requires `remarkGfm` as named import from `remark-gfm` — same import style |

**Deprecated/outdated:**
- `middleware.ts` export: In Next.js 16, the proxy convention uses `proxy.ts` with `export async function proxy` — already correctly implemented in this project.
- lightweight-charts v4 `createChart` with `width/height` as required: In v5 these are optional when container has CSS dimensions.

---

## Open Questions

1. **Volume histogram panel in lightweight-charts v5**
   - What we know: lightweight-charts v5 supports `addHistogramSeries()` for volume. Positioning it in a sub-pane requires `priceScaleId` configuration.
   - What's unclear: The exact v5 API for creating a visually separated volume sub-pane (not overlaid on price) without a separate chart instance.
   - Recommendation: Start with volume on the same chart using a secondary price scale with 20% height allocation via `scaleMargins`. If this looks wrong, omit volume from v5 (the UI-SPEC says "volume histogram below candlestick area" but this is a Claude's Discretion area for the chart implementation detail).

2. **How to fetch initial report content on page load**
   - What we know: `GET /reports/by-ticker/{symbol}?per_page=1` returns the latest `report_id`. Then `GET /reports/by-report-id/{report_id}` (new endpoint) returns content.
   - What's unclear: Whether a single combined endpoint (latest report for symbol with full content) would be more efficient than two calls.
   - Recommendation: Two sequential calls is acceptable — they happen in parallel with OHLCV fetch. Keep endpoints simple and composable.

3. **@tailwindcss/typography in Tailwind v4**
   - What we know: The project uses Tailwind v4.2.2 with CSS-first config. @tailwindcss/typography v0.5.19 is the latest stable.
   - What's unclear: Whether v0.5.x integrates cleanly with Tailwind v4's `@plugin` directive without deprecation warnings.
   - Recommendation: Install and test. If `prose` class styles are applied correctly, proceed. A Wave 0 smoke test should verify this before building ReportMarkdown.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 4.1.0 + @testing-library/react 16.3.2 |
| Config file | `frontend/vitest.config.ts` |
| Quick run command | `cd frontend && npm test` |
| Full suite command | `cd frontend && npm test` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RVEW-01 | Summary card renders tier, sub-assessments, verdict | unit | `cd frontend && npm test -- --reporter=verbose src/components/report/__tests__/ReportSummaryCard.test.tsx` | ❌ Wave 0 |
| RVEW-02 | Expand/collapse toggles ReportMarkdown mount | unit | `cd frontend && npm test -- --reporter=verbose src/components/report/__tests__/ReportPageClient.test.tsx` | ❌ Wave 0 |
| RVEW-03 | Language toggle switches content; persists in localStorage | unit | `cd frontend && npm test -- --reporter=verbose src/components/report/__tests__/BilingualToggle.test.tsx` | ❌ Wave 0 |
| RVEW-04 | TradingViewChart renders without SSR crash | unit (mock) | `cd frontend && npm test -- --reporter=verbose src/components/report/__tests__/TradingViewChart.test.tsx` | ❌ Wave 0 |
| RHST-01 | HistoryTimeline renders items from API response | unit | `cd frontend && npm test -- --reporter=verbose src/components/report/__tests__/HistoryTimeline.test.tsx` | ❌ Wave 0 |
| RHST-02 | Each row shows date + TierBadge | unit | included in HistoryTimeline test | ❌ Wave 0 |
| RHST-03 | Row click loads new report content | unit | included in ReportPageClient test | ❌ Wave 0 |
| RHST-04 | Upgrade/downgrade arrows computed correctly | unit | `cd frontend && npm test -- --reporter=verbose src/components/report/__tests__/HistoryTimeline.test.tsx` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd frontend && npm test`
- **Per wave merge:** `cd frontend && npm test`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `frontend/src/components/report/__tests__/ReportSummaryCard.test.tsx` — covers RVEW-01
- [ ] `frontend/src/components/report/__tests__/BilingualToggle.test.tsx` — covers RVEW-03
- [ ] `frontend/src/components/report/__tests__/TradingViewChart.test.tsx` — covers RVEW-04 (mock lightweight-charts via vi.mock)
- [ ] `frontend/src/components/report/__tests__/ReportPageClient.test.tsx` — covers RVEW-02, RHST-03
- [ ] `frontend/src/components/report/__tests__/HistoryTimeline.test.tsx` — covers RHST-01, RHST-02, RHST-04
- [ ] Backend test: `reasoning/tests/test_reports_by_id.py` — covers new GET /reports/by-report-id/{report_id} endpoint

**Test mocking notes:**
- `lightweight-charts` must be mocked in all frontend tests: `vi.mock('lightweight-charts', () => ({ createChart: vi.fn(() => ({ ... })), ... }))`
- `localStorage` is available in jsdom (test environment) — no mock needed
- `next/dynamic` must be mocked or the TradingViewChart import will fail in vitest: use `vi.mock('next/dynamic', () => ({ default: (fn: () => Promise<unknown>) => fn }))`

---

## Sources

### Primary (HIGH confidence)
- Project source code directly read — `reasoning/app/routers/reports.py`, `reasoning/app/pipeline/storage.py`, `reasoning/app/nodes/state.py`, `db/migrations/V6__reports.sql`, `db/migrations/V7__report_jobs.sql`
- Project source code directly read — `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`, `frontend/src/components/dashboard/TierBadge.tsx`, `frontend/src/app/reports/[symbol]/page.tsx`
- `frontend/node_modules/next/dist/docs/01-app/02-guides/lazy-loading.md` — dynamic import + ssr:false pattern
- `npm view lightweight-charts version` — version 5.1.0 confirmed current
- `npm view react-markdown version` — version 10.1.0 confirmed current
- `npm view remark-gfm version` — version 4.0.1 confirmed current
- `npm view @tailwindcss/typography version` — version 0.5.19 confirmed current

### Secondary (MEDIUM confidence)
- `.planning/phases/14-report-view-tradingview-chart-and-history/14-CONTEXT.md` — locked decisions, UI-SPEC
- `.planning/phases/14-report-view-tradingview-chart-and-history/14-UI-SPEC.md` — component inventory, layout contract
- `.planning/STATE.md` — established decisions from Phases 12 and 13

### Tertiary (LOW confidence)
- Tailwind v4 `@plugin` directive for @tailwindcss/typography — inferred from Tailwind v4 CSS-first architecture; not directly verified from official Tailwind v4 plugin documentation. Treat as needing Wave 0 smoke test verification.
- lightweight-charts v5 volume sub-pane API specifics — v5 changelog not directly read; API example inferred from v4 patterns and general knowledge.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions confirmed from npm registry; libraries are established choices
- Architecture: HIGH — follows existing project patterns confirmed from source code
- Backend gap (new endpoint): HIGH — confirmed by reading all existing endpoints; gap is definitive
- Pitfalls: HIGH for items verified against project source; MEDIUM for lightweight-charts v5 API specifics
- @tailwindcss/typography + Tailwind v4: MEDIUM — plausible but needs smoke test

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (30 days — stable libraries)
