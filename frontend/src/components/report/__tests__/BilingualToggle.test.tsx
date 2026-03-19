import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { BilingualToggle } from '../BilingualToggle'

describe('BilingualToggle', () => {
  it('renders VI and EN buttons', () => {
    render(<BilingualToggle lang="vi" onLanguageChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'VI' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'EN' })).toBeInTheDocument()
  })

  it('VI button has aria-pressed="true" when lang="vi"', () => {
    render(<BilingualToggle lang="vi" onLanguageChange={vi.fn()} />)
    const viButton = screen.getByRole('button', { name: 'VI' })
    expect(viButton).toHaveAttribute('aria-pressed', 'true')
  })

  it('EN button has aria-pressed="true" when lang="en"', () => {
    render(<BilingualToggle lang="en" onLanguageChange={vi.fn()} />)
    const enButton = screen.getByRole('button', { name: 'EN' })
    expect(enButton).toHaveAttribute('aria-pressed', 'true')
  })

  it('clicking EN button calls onLanguageChange with "en"', () => {
    const onLanguageChange = vi.fn()
    render(<BilingualToggle lang="vi" onLanguageChange={onLanguageChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'EN' }))
    expect(onLanguageChange).toHaveBeenCalledWith('en')
  })

  it('has aria-label="Report language"', () => {
    const { container } = render(<BilingualToggle lang="vi" onLanguageChange={vi.fn()} />)
    const group = container.querySelector('[aria-label="Report language"]')
    expect(group).toBeInTheDocument()
  })

  it('has fixed positioning class', () => {
    const { container } = render(<BilingualToggle lang="vi" onLanguageChange={vi.fn()} />)
    const group = container.querySelector('[aria-label="Report language"]')
    expect(group?.className).toContain('fixed')
  })
})
