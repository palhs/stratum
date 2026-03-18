import { TickerCard } from './TickerCard'
import type { TickerData } from '@/lib/types'

export function WatchlistGrid({ tickers }: { tickers: TickerData[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6" aria-live="polite">
      {tickers.map((ticker) => (
        <TickerCard key={ticker.symbol} ticker={ticker} />
      ))}
    </div>
  )
}
