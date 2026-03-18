'use client'

import Link from 'next/link'
import { Card, CardContent } from '@/components/ui/card'
import { TierBadge } from './TierBadge'
import { Sparkline } from './Sparkline'
import { StepList } from './StepList'
import { GenerateButton } from './GenerateButton'
import type { TickerData, StepStatus } from '@/lib/types'

interface TickerCardProps {
  ticker: TickerData
  isGenerating: boolean
  steps: Map<string, StepStatus> | null
  onGenerate: (symbol: string, assetType: string) => void
}

export function TickerCard({ ticker, isGenerating, steps, onGenerate }: TickerCardProps) {
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
          {/* Header: symbol + name — always visible */}
          <div>
            <p className="text-xl font-bold">{ticker.symbol}</p>
            <p className="text-sm text-muted-foreground">{ticker.name}</p>
          </div>

          {/* Tier badge — always visible */}
          <div className="flex justify-center">
            <TierBadge tier={ticker.lastReport?.tier ?? null} />
          </div>

          {/* Collapsible section: either sparkline+date+button OR step list */}
          <div className="grid transition-all duration-300" style={{ gridTemplateRows: isGenerating ? '1fr' : '1fr' }}>
            <div className="overflow-hidden">
              {isGenerating && steps ? (
                <StepList steps={steps} />
              ) : (
                <>
                  {closeData.length >= 2 && (
                    <Sparkline data={closeData} />
                  )}
                  <p className="text-xs text-muted-foreground mt-3">
                    {lastReportDate ? `Last report: ${lastReportDate}` : 'No reports yet'}
                  </p>
                  <div className="mt-3">
                    <GenerateButton
                      onClick={() => onGenerate(ticker.symbol, ticker.asset_type)}
                    />
                  </div>
                </>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
