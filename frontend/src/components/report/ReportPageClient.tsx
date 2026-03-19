'use client'

import { useState, useEffect, useCallback } from 'react'
import dynamic from 'next/dynamic'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { toast } from 'sonner'
import { ReportSummaryCard } from './ReportSummaryCard'
import { BilingualToggle } from './BilingualToggle'
import { ReportMarkdown } from './ReportMarkdown'
import { HistoryTimeline } from './HistoryTimeline'
import { ReportPageSkeleton } from './ReportPageSkeleton'
import { getOhlcv, getReportHistory, getReportContent } from '@/lib/api'
import type { OHLCVPoint, ReportHistoryItem, ReportContentResponse } from '@/lib/types'

const TradingViewChart = dynamic(
  () => import('./TradingViewChart'),
  {
    ssr: false,
    loading: () => <Skeleton className="w-full h-[260px] md:h-[400px] rounded-lg" />,
  }
)

interface ReportPageClientProps {
  symbol: string
  accessToken: string
}

export function ReportPageClient({ symbol, accessToken }: ReportPageClientProps) {
  // Language state — persisted in localStorage, default vi
  const [lang, setLang] = useState<'vi' | 'en'>(() => {
    if (typeof window === 'undefined') return 'vi'
    return (localStorage.getItem('stratum-report-lang') as 'vi' | 'en') ?? 'vi'
  })

  // Report state
  const [report, setReport] = useState<ReportContentResponse | null>(null)
  const [isExpanded, setIsExpanded] = useState(false)
  const [reportLoading, setReportLoading] = useState(true)
  const [reportError, setReportError] = useState<string | null>(null)

  // OHLCV state
  const [ohlcv, setOhlcv] = useState<OHLCVPoint[]>([])
  const [ohlcvError, setOhlcvError] = useState(false)

  // History state
  const [historyItems, setHistoryItems] = useState<ReportHistoryItem[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyPage, setHistoryPage] = useState(1)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [activeReportId, setActiveReportId] = useState<number | null>(null)

  const handleLangChange = useCallback((next: 'vi' | 'en') => {
    setLang(next)
    localStorage.setItem('stratum-report-lang', next)
  }, [])

  // Initial load: fetch OHLCV + history + latest report content
  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        // Fetch OHLCV and history in parallel
        const [ohlcvRes, historyRes] = await Promise.all([
          getOhlcv(symbol, accessToken).catch(() => {
            setOhlcvError(true)
            return null
          }),
          getReportHistory(symbol, accessToken, 1, 10),
        ])

        if (cancelled) return

        if (ohlcvRes) {
          setOhlcv(ohlcvRes.data)
        }

        setHistoryItems(historyRes.items)
        setHistoryTotal(historyRes.total)

        // Load latest report content
        if (historyRes.items.length > 0) {
          const latestId = historyRes.items[0].report_id
          setActiveReportId(latestId)
          const content = await getReportContent(latestId, accessToken)
          if (!cancelled) {
            setReport(content)
          }
        }
      } catch (err) {
        if (!cancelled) {
          setReportError('Could not load report. Refresh the page or return to the dashboard.')
          toast.error('Failed to load report')
        }
      } finally {
        if (!cancelled) {
          setReportLoading(false)
          setHistoryLoading(false)
        }
      }
    }

    load()
    return () => { cancelled = true }
  }, [symbol, accessToken])

  // Select a historical report
  const handleSelectReport = useCallback(async (reportId: number) => {
    setActiveReportId(reportId)
    setReportLoading(true)
    setReportError(null)
    setIsExpanded(false)
    try {
      const content = await getReportContent(reportId, accessToken)
      setReport(content)
    } catch {
      setReportError('Could not load report. Refresh the page or return to the dashboard.')
      toast.error('Failed to load report')
    } finally {
      setReportLoading(false)
    }
  }, [accessToken])

  // Load more history
  const handleLoadMore = useCallback(async () => {
    const nextPage = historyPage + 1
    setHistoryLoading(true)
    try {
      const res = await getReportHistory(symbol, accessToken, nextPage, 10)
      setHistoryItems(prev => [...prev, ...res.items])
      setHistoryTotal(res.total)
      setHistoryPage(nextPage)
    } catch {
      toast.error('Could not load report history. Try refreshing.')
    } finally {
      setHistoryLoading(false)
    }
  }, [symbol, accessToken, historyPage])

  // Compute current markdown based on language
  const currentMarkdown = report
    ? (lang === 'vi' ? report.report_markdown_vi : report.report_markdown_en) ?? ''
    : ''

  const currentVerdict = report?.verdict ?? ''

  if (reportLoading && !report) {
    return (
      <div className="min-h-screen bg-background px-4 py-6 md:px-6 md:py-8 max-w-4xl mx-auto">
        <Button variant="ghost" asChild className="mb-4">
          <Link href="/">Back to dashboard</Link>
        </Button>
        <h1 className="text-xl font-bold mb-6">{symbol}</h1>
        <ReportPageSkeleton />
      </div>
    )
  }

  if (reportError && !report) {
    return (
      <div className="min-h-screen bg-background px-4 py-6 md:px-6 md:py-8 max-w-4xl mx-auto">
        <Button variant="ghost" asChild className="mb-4">
          <Link href="/">Back to dashboard</Link>
        </Button>
        <h1 className="text-xl font-bold mb-6">{symbol}</h1>
        <div className="text-center py-12">
          <h2 className="text-xl font-bold mb-2">No report available</h2>
          <p className="text-muted-foreground">Generate a report from the dashboard to see the full analysis here.</p>
          <Button variant="outline" asChild className="mt-4">
            <Link href="/">Back to dashboard</Link>
          </Button>
        </div>
      </div>
    )
  }

  if (!report) {
    return (
      <div className="min-h-screen bg-background px-4 py-6 md:px-6 md:py-8 max-w-4xl mx-auto">
        <Button variant="ghost" asChild className="mb-4">
          <Link href="/">Back to dashboard</Link>
        </Button>
        <h1 className="text-xl font-bold mb-6">{symbol}</h1>
        <div className="text-center py-12">
          <h2 className="text-xl font-bold mb-2">No report available</h2>
          <p className="text-muted-foreground">Generate a report from the dashboard to see the full analysis here.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background px-4 py-6 md:px-6 md:py-8 max-w-4xl mx-auto">
      <BilingualToggle lang={lang} onLanguageChange={handleLangChange} />

      <Button variant="ghost" asChild className="mb-4">
        <Link href="/">Back to dashboard</Link>
      </Button>
      <h1 className="text-xl font-bold mb-6">{symbol}</h1>

      {/* Summary Card */}
      <ReportSummaryCard
        tier={report.tier}
        verdict={currentVerdict}
        macroAssessment={report.macro_assessment}
        valuationAssessment={report.valuation_assessment}
        structureAssessment={report.structure_assessment}
        isExpanded={isExpanded}
        onExpandToggle={() => setIsExpanded(prev => !prev)}
      />

      {/* TradingView Chart */}
      <div className="mt-6">
        {ohlcvError ? (
          <div className="w-full h-[260px] md:h-[400px] rounded-lg border border-border flex items-center justify-center">
            <p className="text-sm text-muted-foreground">Chart unavailable. Price data could not be loaded.</p>
          </div>
        ) : (
          <TradingViewChart data={ohlcv} />
        )}
      </div>

      {/* Expanded Report Markdown */}
      {isExpanded && currentMarkdown && (
        <div className="mt-6 animate-in fade-in duration-200">
          <ReportMarkdown content={currentMarkdown} lang={lang} />
        </div>
      )}

      {/* History Timeline */}
      <div className="mt-8">
        <HistoryTimeline
          items={historyItems}
          activeReportId={activeReportId}
          symbol={symbol}
          hasMore={historyItems.length < historyTotal}
          loading={historyLoading}
          onSelectReport={handleSelectReport}
          onLoadMore={handleLoadMore}
        />
      </div>
    </div>
  )
}
