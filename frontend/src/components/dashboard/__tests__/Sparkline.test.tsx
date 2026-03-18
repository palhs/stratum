import { render, container as testContainer } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Sparkline } from '../Sparkline'

describe('Sparkline', () => {
  it('renders SVG with polyline element when given valid data array', () => {
    const { container } = render(<Sparkline data={[10, 20, 15, 25, 30]} />)
    const svg = container.querySelector('svg')
    expect(svg).toBeInTheDocument()
    const polyline = container.querySelector('polyline')
    expect(polyline).toBeInTheDocument()
  })

  it('returns null when data has fewer than 2 points', () => {
    const { container } = render(<Sparkline data={[10]} />)
    expect(container.querySelector('svg')).not.toBeInTheDocument()
  })

  it('uses green stroke (#16a34a) when last price >= first price', () => {
    const { container } = render(<Sparkline data={[10, 5, 20]} />)
    const polyline = container.querySelector('polyline')
    expect(polyline?.getAttribute('stroke')).toBe('#16a34a')
  })

  it('uses red stroke (#dc2626) when last price < first price', () => {
    const { container } = render(<Sparkline data={[20, 15, 10]} />)
    const polyline = container.querySelector('polyline')
    expect(polyline?.getAttribute('stroke')).toBe('#dc2626')
  })

  it('handles flat data (all same values) without division by zero', () => {
    const { container } = render(<Sparkline data={[10, 10, 10, 10]} />)
    const svg = container.querySelector('svg')
    expect(svg).toBeInTheDocument()
    const polyline = container.querySelector('polyline')
    expect(polyline).toBeInTheDocument()
    // Should not throw and should render without NaN
    const points = polyline?.getAttribute('points') ?? ''
    expect(points).not.toContain('NaN')
  })
})
