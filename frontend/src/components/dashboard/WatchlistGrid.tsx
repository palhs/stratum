import { TickerCard } from './TickerCard'
import type { TickerData, StepStatus } from '@/lib/types'

interface WatchlistGridProps {
  tickers: TickerData[]
  generatingSymbols: Set<string>
  generationSteps: Map<string, Map<string, StepStatus>>
  onGenerate: (symbol: string, assetType: string) => void
}

export function WatchlistGrid({ tickers, generatingSymbols, generationSteps, onGenerate }: WatchlistGridProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6" aria-live="polite">
      {tickers.map((ticker) => (
        <TickerCard
          key={ticker.symbol}
          ticker={ticker}
          isGenerating={generatingSymbols.has(ticker.symbol)}
          steps={generationSteps.get(ticker.symbol) ?? null}
          onGenerate={onGenerate}
        />
      ))}
    </div>
  )
}
