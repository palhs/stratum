'use client'

import { useEffect, useState, useCallback } from 'react'
import { toast } from 'sonner'
import { getWatchlist, getOhlcv, getLastReport, addTickerToWatchlist } from '@/lib/api'
import { WatchlistGrid } from './WatchlistGrid'
import { WatchlistGridSkeleton } from './WatchlistGridSkeleton'
import { EmptyState } from './EmptyState'
import { ErrorState } from './ErrorState'
import type { TickerData } from '@/lib/types'

export function DashboardClient({ accessToken }: { accessToken: string }) {
  const [tickers, setTickers] = useState<TickerData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentSymbols, setCurrentSymbols] = useState<string[]>([])

  const loadDashboard = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const watchlist = await getWatchlist(accessToken)
      const symbols = watchlist.tickers.map(t => t.symbol)
      setCurrentSymbols(symbols)

      if (watchlist.tickers.length === 0) {
        setTickers([])
        return
      }

      const enriched = await Promise.all(
        watchlist.tickers.map(async (t) => {
          const [ohlcvRes, reportRes] = await Promise.all([
            getOhlcv(t.symbol, accessToken).catch(() => null),
            getLastReport(t.symbol, accessToken).catch(() => null),
          ])
          const lastReport = reportRes?.items?.[0] ?? null
          return {
            symbol: t.symbol,
            name: t.name,
            asset_type: t.asset_type,
            ohlcv: ohlcvRes?.data ?? null,
            lastReport: lastReport ? { tier: lastReport.tier, generated_at: lastReport.generated_at } : null,
          } satisfies TickerData
        })
      )
      setTickers(enriched)
    } catch {
      if (tickers.length > 0) {
        toast.error('Refresh failed \u2014 showing cached data')
      } else {
        setError('Check your connection and try again.')
        toast.error('Failed to load dashboard')
      }
    } finally {
      setLoading(false)
    }
  }, [accessToken])

  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  async function handleAddTicker(symbol: string) {
    try {
      await addTickerToWatchlist(currentSymbols, symbol, accessToken)
      await loadDashboard()
    } catch {
      toast.error(`Couldn't add ${symbol}`)
    }
  }

  if (loading) return <WatchlistGridSkeleton />
  if (error && tickers.length === 0) return <ErrorState message={error} onRetry={loadDashboard} />
  if (tickers.length === 0) return <EmptyState onAddTicker={handleAddTicker} />
  return <WatchlistGrid tickers={tickers} />
}
