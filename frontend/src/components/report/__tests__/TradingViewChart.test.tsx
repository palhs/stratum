import { render } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Use vi.hoisted to create mocks that can be safely referenced in vi.mock factory
const { mockSetData, mockRemove, mockApplyOptions, mockCreateChart } = vi.hoisted(() => {
  const mockSetData = vi.fn()
  const mockApplyOptions = vi.fn()
  const mockRemove = vi.fn()
  const mockAddSeries = vi.fn(() => ({ setData: mockSetData }))
  const mockSetVisibleRange = vi.fn()
  const mockTimeScale = vi.fn(() => ({ setVisibleRange: mockSetVisibleRange }))
  const mockPriceScale = vi.fn(() => ({ applyOptions: mockApplyOptions }))

  const mockChart = {
    addSeries: mockAddSeries,
    timeScale: mockTimeScale,
    priceScale: mockPriceScale,
    applyOptions: vi.fn(),
    remove: mockRemove,
  }

  const mockCreateChart = vi.fn(() => mockChart)

  return { mockSetData, mockRemove, mockApplyOptions, mockCreateChart }
})

vi.mock('lightweight-charts', () => ({
  createChart: mockCreateChart,
  ColorType: { Solid: 'solid' },
  CrosshairMode: { Normal: 0 },
  CandlestickSeries: {},
  LineSeries: {},
  HistogramSeries: {},
}))

import TradingViewChart from '../TradingViewChart'

const sampleData = Array.from({ length: 10 }, (_, i) => ({
  time: 1700000000 + i * 86400,
  close: 100 + i,
  open: 99 + i,
  high: 102 + i,
  low: 98 + i,
  volume: 1000 + i * 100,
  ma50: i >= 1 ? 100 + i * 0.5 : null,
  ma200: i >= 2 ? 100 + i * 0.3 : null,
}))

describe('TradingViewChart', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls createChart when data is non-empty', () => {
    render(<TradingViewChart data={sampleData} />)
    expect(mockCreateChart).toHaveBeenCalledOnce()
  })

  it('calls chart.remove() on unmount', () => {
    const { unmount } = render(<TradingViewChart data={sampleData} />)
    unmount()
    expect(mockRemove).toHaveBeenCalledOnce()
  })

  it('container has aria-label "Price chart"', () => {
    render(<TradingViewChart data={sampleData} />)
    const el = document.querySelector('[aria-label="Price chart"]')
    expect(el).toBeInTheDocument()
  })

  it('container has responsive height classes', () => {
    render(<TradingViewChart data={sampleData} />)
    const el = document.querySelector('[aria-label="Price chart"]')
    expect(el?.className).toContain('h-[260px]')
  })

  it('does not call createChart when data is empty', () => {
    render(<TradingViewChart data={[]} />)
    expect(mockCreateChart).not.toHaveBeenCalled()
  })
})
