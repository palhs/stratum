'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { toast } from 'sonner'
import { getWatchlist, getOhlcv, getLastReport, addTickerToWatchlist, generateReport } from '@/lib/api'
import { WatchlistGrid } from './WatchlistGrid'
import { WatchlistGridSkeleton } from './WatchlistGridSkeleton'
import { EmptyState } from './EmptyState'
import { ErrorState } from './ErrorState'
import { STEP_ORDER } from './StepList'
import type { TickerData, StepStatus } from '@/lib/types'

export function DashboardClient({ accessToken }: { accessToken: string }) {
  const [tickers, setTickers] = useState<TickerData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentSymbols, setCurrentSymbols] = useState<string[]>([])
  const [generatingSymbols, setGeneratingSymbols] = useState<Set<string>>(new Set())
  const [generationSteps, setGenerationSteps] = useState<Map<string, Map<string, StepStatus>>>(new Map())
  const eventSourcesRef = useRef<Map<string, EventSource>>(new Map())

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

  useEffect(() => {
    return () => {
      eventSourcesRef.current.forEach(es => es.close())
    }
  }, [])

  async function handleAddTicker(symbol: string) {
    try {
      await addTickerToWatchlist(currentSymbols, symbol, accessToken)
      await loadDashboard()
    } catch {
      toast.error(`Couldn't add ${symbol}`)
    }
  }

  async function handleGenerate(symbol: string, assetType: string) {
    try {
      const { job_id } = await generateReport(symbol, assetType, accessToken)

      // Initialize step state — all pending
      const initialSteps = new Map<string, StepStatus>(STEP_ORDER.map(n => [n, 'pending']))
      setGeneratingSymbols(prev => new Set(prev).add(symbol))
      setGenerationSteps(prev => new Map(prev).set(symbol, initialSteps))

      // Open SSE stream — connect directly to FastAPI via NEXT_PUBLIC_API_URL
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? ''
      const es = new EventSource(`${apiBase}/reports/stream/${job_id}`)
      eventSourcesRef.current.set(symbol, es)

      es.addEventListener('node_transition', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        setGenerationSteps(prev => {
          const current = prev.get(symbol)
          if (!current) return prev
          const newSteps = new Map(current)
          if (data.event_type === 'node_start') {
            newSteps.set(data.node, 'in_progress')
          } else if (data.event_type === 'node_complete') {
            newSteps.set(data.node, data.error ? 'failed' : 'completed')
          }
          return new Map(prev).set(symbol, newSteps)
        })
      })

      es.addEventListener('complete', () => {
        es.close()
        eventSourcesRef.current.delete(symbol)
        setGeneratingSymbols(prev => { const next = new Set(prev); next.delete(symbol); return next })
        setGenerationSteps(prev => { const next = new Map(prev); next.delete(symbol); return next })
        // Refresh dashboard to get updated tier badge and last report date
        loadDashboard()
        toast.success(`${symbol} report ready`)
      })

      es.onerror = () => {
        es.close()
        eventSourcesRef.current.delete(symbol)
        toast.error('Report generation failed')
        // Hold expanded briefly (4 seconds) so user sees which step failed, then collapse
        setTimeout(() => {
          setGeneratingSymbols(prev => { const next = new Set(prev); next.delete(symbol); return next })
          setGenerationSteps(prev => { const next = new Map(prev); next.delete(symbol); return next })
        }, 4000)
      }
    } catch {
      toast.error(`Couldn't start generation for ${symbol}`)
    }
  }

  if (loading) return <WatchlistGridSkeleton />
  if (error && tickers.length === 0) return <ErrorState message={error} onRetry={loadDashboard} />
  if (tickers.length === 0) return <EmptyState onAddTicker={handleAddTicker} />
  return (
    <WatchlistGrid
      tickers={tickers}
      generatingSymbols={generatingSymbols}
      generationSteps={generationSteps}
      onGenerate={handleGenerate}
    />
  )
}
