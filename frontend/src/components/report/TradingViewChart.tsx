'use client'

import { useEffect, useRef } from 'react'
import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from 'lightweight-charts'
import type { OHLCVPoint } from '@/lib/types'
import type { UTCTimestamp } from 'lightweight-charts'

export default function TradingViewChart({ data }: { data: OHLCVPoint[] }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#71717a',
      },
      grid: {
        vertLines: { color: '#27272a' },
        horzLines: { color: '#27272a' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    })

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#14b8a6',
      downColor: '#f43f5e',
      borderVisible: false,
      wickUpColor: '#14b8a6',
      wickDownColor: '#f43f5e',
    })

    const ma50Series = chart.addSeries(LineSeries, {
      color: '#3b82f6',
      lineWidth: 2,
      priceLineVisible: false,
    })

    const ma200Series = chart.addSeries(LineSeries, {
      color: '#f97316',
      lineWidth: 2,
      priceLineVisible: false,
    })

    // Volume histogram on secondary price scale
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: 'rgba(113, 113, 122, 0.3)',
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    })
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })

    const candleData = data.map(p => ({
      time: p.time as UTCTimestamp,
      open: p.open ?? p.close,
      high: p.high ?? p.close,
      low: p.low ?? p.close,
      close: p.close,
    }))

    const ma50Data = data
      .filter(p => p.ma50 != null)
      .map(p => ({ time: p.time as UTCTimestamp, value: p.ma50! }))

    const ma200Data = data
      .filter(p => p.ma200 != null)
      .map(p => ({ time: p.time as UTCTimestamp, value: p.ma200! }))

    const volumeData = data
      .filter(p => p.volume != null)
      .map(p => ({ time: p.time as UTCTimestamp, value: p.volume! }))

    candlestickSeries.setData(candleData)
    ma50Series.setData(ma50Data)
    ma200Series.setData(ma200Data)
    volumeSeries.setData(volumeData)

    if (data.length > 52) {
      chart.timeScale().setVisibleRange({
        from: data[data.length - 52].time as UTCTimestamp,
        to: data[data.length - 1].time as UTCTimestamp,
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
      aria-label="Price chart"
    />
  )
}
