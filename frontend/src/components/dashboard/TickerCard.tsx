import Link from 'next/link'
import { Card, CardContent } from '@/components/ui/card'
import { TierBadge } from './TierBadge'
import { Sparkline } from './Sparkline'
import type { TickerData } from '@/lib/types'

export function TickerCard({ ticker }: { ticker: TickerData }) {
  const closeData = ticker.ohlcv?.map(p => p.close) ?? []
  const lastReportDate = ticker.lastReport?.generated_at
    ? new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(ticker.lastReport.generated_at))
    : null

  return (
    <Link
      href={`/reports/${ticker.symbol}`}
      className="block focus-visible:ring-2 focus-visible:ring-ring rounded-xl"
    >
      <Card className="hover:shadow-md hover:border-foreground/20 transition-shadow p-4 space-y-3">
        <CardContent className="p-0 space-y-3">
          <div>
            <p className="text-xl font-bold">{ticker.symbol}</p>
            <p className="text-sm text-muted-foreground">{ticker.name}</p>
          </div>
          <div className="flex justify-center">
            <TierBadge tier={ticker.lastReport?.tier ?? null} />
          </div>
          {closeData.length >= 2 && (
            <Sparkline data={closeData} />
          )}
          <p className="text-xs text-muted-foreground">
            {lastReportDate ? `Last report: ${lastReportDate}` : 'No reports yet'}
          </p>
        </CardContent>
      </Card>
    </Link>
  )
}
