import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { GenerateButton } from '../GenerateButton'

describe('GenerateButton', () => {
  it('renders with "Generate Report" label', () => {
    render(<GenerateButton onClick={() => {}} />)
    expect(screen.getByRole('button', { name: 'Generate Report' })).toBeInTheDocument()
  })

  it('calls onClick when clicked', () => {
    const onClick = vi.fn()
    render(<GenerateButton onClick={onClick} />)
    fireEvent.click(screen.getByRole('button'))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('is disabled when disabled prop is true', () => {
    render(<GenerateButton onClick={() => {}} disabled />)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('stops event propagation on click', () => {
    const parentClick = vi.fn()
    const onClick = vi.fn()
    render(
      <div onClick={parentClick}>
        <GenerateButton onClick={onClick} />
      </div>
    )
    fireEvent.click(screen.getByRole('button'))
    expect(onClick).toHaveBeenCalledOnce()
    expect(parentClick).not.toHaveBeenCalled()
  })
})
