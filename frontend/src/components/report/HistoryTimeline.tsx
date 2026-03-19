'use client'

import { TierBadge } from '@/components/dashboard/TierBadge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ArrowUp, ArrowDown } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import type { ReportHistoryItem } from '@/lib/types'
import { cn } from '@/lib/utils'

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
  if (curr < prev) return 'up'
  if (curr > prev) return 'down'
  return 'none'
}

interface HistoryTimelineProps {
  items: ReportHistoryItem[]
  activeReportId: number | null
  symbol: string
  hasMore: boolean
  loading: boolean
  onSelectReport: (reportId: number) => void
  onLoadMore: () => void
}

export function HistoryTimeline({
  items,
  activeReportId,
  symbol,
  hasMore,
  loading,
  onSelectReport,
  onLoadMore,
}: HistoryTimelineProps) {
  if (loading && items.length === 0) {
    return (
      <div className="flex flex-col gap-2">
        <h2 className="text-xl font-bold mb-4">Report History</h2>
        <Skeleton className="h-11 w-full rounded" />
        <Skeleton className="h-11 w-full rounded" />
        <Skeleton className="h-11 w-full rounded" />
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div>
        <h2 className="text-xl font-bold mb-4">Report History</h2>
        <p className="text-sm text-muted-foreground">No report history for {symbol} yet.</p>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Report History</h2>
      <ul>
        {items.map((item, index) => {
          const previousTier = index < items.length - 1 ? items[index + 1].tier : null
          const change = getTierChange(item.tier, previousTier)
          const isActive = item.report_id === activeReportId

          return (
            <li key={item.report_id}>
              <button
                type="button"
                className={cn(
                  'w-full flex items-center gap-3 py-3 border-b border-border min-h-[44px] cursor-pointer',
                  'hover:bg-muted/30 focus-visible:ring-2 focus-visible:ring-ring',
                  isActive && 'border-l-2 border-primary bg-muted/50'
                )}
                onClick={() => onSelectReport(item.report_id)}
              >
                <span className="text-sm text-muted-foreground w-20 shrink-0">
                  {format(parseISO(item.generated_at), 'dd MMM yyyy')}
                </span>
                <TierBadge tier={item.tier} />
                <span className="text-sm text-foreground flex-1 text-left line-clamp-1">
                  {item.verdict}
                </span>
                {change === 'up' && (
                  <ArrowUp
                    className="w-4 h-4 text-teal-600 dark:text-teal-400 shrink-0"
                    aria-label={`Upgraded from ${previousTier} to ${item.tier}`}
                  />
                )}
                {change === 'down' && (
                  <ArrowDown
                    className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0"
                    aria-label={`Downgraded from ${previousTier} to ${item.tier}`}
                  />
                )}
              </button>
            </li>
          )
        })}
      </ul>
      {hasMore && (
        <Button
          variant="outline"
          className="w-full mt-4"
          onClick={onLoadMore}
          disabled={loading}
        >
          Load more reports
        </Button>
      )}
    </div>
  )
}
