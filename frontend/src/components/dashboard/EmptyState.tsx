'use client'

import { Button } from '@/components/ui/button'

const SUGGESTED_TICKERS = ['VNM', 'FPT', 'HPG', 'GLD', 'MWG']

export function EmptyState({ onAddTicker }: { onAddTicker: (symbol: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 space-y-4">
      <h3 className="text-xl font-bold">Your watchlist is empty</h3>
      <p className="text-sm text-muted-foreground">
        Add tickers to start tracking entry quality.
      </p>
      <p className="text-sm text-muted-foreground">Start with a popular ticker:</p>
      <div className="flex flex-wrap gap-2 justify-center">
        {SUGGESTED_TICKERS.map((symbol) => (
          <Button
            key={symbol}
            variant="outline"
            className="min-h-[44px]"
            aria-label={`Add ${symbol} to watchlist`}
            onClick={() => onAddTicker(symbol)}
          >
            {symbol}
          </Button>
        ))}
      </div>
    </div>
  )
}
