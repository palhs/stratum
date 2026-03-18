import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { TierBadge } from '../TierBadge'

describe('TierBadge', () => {
  it('renders "Favorable" text and applies teal classes (bg-teal-100)', () => {
    const { container } = render(<TierBadge tier="Favorable" />)
    expect(screen.getByText('Favorable')).toBeInTheDocument()
    const badge = container.querySelector('[data-slot="badge"]')
    expect(badge?.className).toContain('bg-teal-100')
  })

  it('renders "Avoid" text and applies rose classes (bg-rose-100)', () => {
    const { container } = render(<TierBadge tier="Avoid" />)
    expect(screen.getByText('Avoid')).toBeInTheDocument()
    const badge = container.querySelector('[data-slot="badge"]')
    expect(badge?.className).toContain('bg-rose-100')
  })

  it('unknown tier renders with gray fallback classes', () => {
    const { container } = render(<TierBadge tier="Unknown" />)
    expect(screen.getByText('Unknown')).toBeInTheDocument()
    const badge = container.querySelector('[data-slot="badge"]')
    expect(badge?.className).toContain('bg-gray-100')
  })

  it('renders with no-report dash "—" in slate style when tier is undefined/null', () => {
    const { container } = render(<TierBadge tier={null} />)
    expect(screen.getByText('—')).toBeInTheDocument()
    const badge = container.querySelector('[data-slot="badge"]')
    expect(badge?.className).toContain('bg-slate-100')
  })
})
