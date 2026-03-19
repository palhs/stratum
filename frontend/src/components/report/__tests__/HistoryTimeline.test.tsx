import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { HistoryTimeline } from '../HistoryTimeline'
import type { ReportHistoryItem } from '@/lib/types'

const makeItem = (
  report_id: number,
  tier: 'Favorable' | 'Neutral' | 'Cautious' | 'Avoid',
  verdict: string,
  generated_at = '2024-01-15T10:00:00Z'
): ReportHistoryItem => ({ report_id, generated_at, tier, verdict })

const defaultProps = {
  items: [
    makeItem(3, 'Favorable', 'Strong uptrend, good entry.', '2024-03-01T10:00:00Z'),
    makeItem(2, 'Neutral', 'Sideways consolidation.', '2024-02-01T10:00:00Z'),
    makeItem(1, 'Cautious', 'Weak structure detected.', '2024-01-01T10:00:00Z'),
  ],
  activeReportId: 3,
  symbol: 'VCB',
  hasMore: false,
  loading: false,
  onSelectReport: vi.fn(),
  onLoadMore: vi.fn(),
}

describe('HistoryTimeline', () => {
  it('renders "Report History" heading', () => {
    render(<HistoryTimeline {...defaultProps} />)
    expect(screen.getByText('Report History')).toBeInTheDocument()
  })

  it('renders history items with date and tier badge', () => {
    render(<HistoryTimeline {...defaultProps} />)
    expect(screen.getByText('Strong uptrend, good entry.')).toBeInTheDocument()
    expect(screen.getByText('Sideways consolidation.')).toBeInTheDocument()
    expect(screen.getByText('Weak structure detected.')).toBeInTheDocument()
  })

  it('renders tier badges for each item', () => {
    render(<HistoryTimeline {...defaultProps} />)
    expect(screen.getByText('Favorable')).toBeInTheDocument()
    expect(screen.getByText('Neutral')).toBeInTheDocument()
    expect(screen.getByText('Cautious')).toBeInTheDocument()
  })

  it('computes upgrade arrow: first item improved from Neutral to Favorable', () => {
    // items[0] = Favorable (newer), items[1] = Neutral (older)
    // Favorable rank(0) < Neutral rank(1) => upgrade
    render(<HistoryTimeline {...defaultProps} />)
    const upgradeArrow = screen.getByLabelText('Upgraded from Neutral to Favorable')
    expect(upgradeArrow).toBeInTheDocument()
  })

  it('computes downgrade arrow: second item downgraded from Cautious to Neutral', () => {
    // items[1] = Neutral (newer), items[2] = Cautious (older)
    // Neutral rank(1) < Cautious rank(2) => actually upgrade from Cautious to Neutral
    // Wait: items[1].tier=Neutral, previousTier=items[2].tier=Cautious
    // Neutral rank(1) < Cautious rank(2) => upgrade, not downgrade
    // To test downgrade: items=[Cautious(newer), Neutral(older)]
    const downgradeItems = [
      makeItem(2, 'Cautious', 'Entry risky.', '2024-02-01T10:00:00Z'),
      makeItem(1, 'Neutral', 'Sideways.', '2024-01-01T10:00:00Z'),
    ]
    render(
      <HistoryTimeline
        {...defaultProps}
        items={downgradeItems}
        activeReportId={2}
      />
    )
    const downgradeArrow = screen.getByLabelText('Downgraded from Neutral to Cautious')
    expect(downgradeArrow).toBeInTheDocument()
  })

  it('shows no arrow when tiers match', () => {
    const sameItems = [
      makeItem(2, 'Neutral', 'Still neutral.', '2024-02-01T10:00:00Z'),
      makeItem(1, 'Neutral', 'Was neutral.', '2024-01-01T10:00:00Z'),
    ]
    render(<HistoryTimeline {...defaultProps} items={sameItems} activeReportId={2} />)
    expect(screen.queryByLabelText(/Upgraded|Downgraded/)).not.toBeInTheDocument()
  })

  it('shows no arrow for the last (oldest) item in the list', () => {
    const items = [
      makeItem(2, 'Favorable', 'Good.', '2024-02-01T10:00:00Z'),
      makeItem(1, 'Neutral', 'Sideways.', '2024-01-01T10:00:00Z'),
    ]
    render(<HistoryTimeline {...defaultProps} items={items} activeReportId={2} />)
    // Last item (index 1) has no previous, so no arrow for it
    // ArrowUp exists for item 0 (Favorable from Neutral)
    const arrows = screen.getAllByLabelText(/Upgraded|Downgraded/)
    expect(arrows).toHaveLength(1)
  })

  it('calls onSelectReport with report_id when row clicked', () => {
    const onSelectReport = vi.fn()
    render(<HistoryTimeline {...defaultProps} onSelectReport={onSelectReport} />)
    // Click row for report_id=2 (Neutral)
    const rows = screen.getAllByRole('button')
    fireEvent.click(rows[1]) // index 1 = second item (report_id=2)
    expect(onSelectReport).toHaveBeenCalledWith(2)
  })

  it('active row has border-primary class', () => {
    render(<HistoryTimeline {...defaultProps} activeReportId={3} />)
    // First row is active (report_id=3)
    const rows = screen.getAllByRole('button')
    expect(rows[0].className).toContain('border-primary')
  })

  it('shows "Load more reports" button when hasMore=true', () => {
    render(<HistoryTimeline {...defaultProps} hasMore={true} />)
    expect(screen.getByText('Load more reports')).toBeInTheDocument()
  })

  it('does not show "Load more reports" button when hasMore=false', () => {
    render(<HistoryTimeline {...defaultProps} hasMore={false} />)
    expect(screen.queryByText('Load more reports')).not.toBeInTheDocument()
  })

  it('shows empty state message when items=[]', () => {
    render(
      <HistoryTimeline
        {...defaultProps}
        items={[]}
        activeReportId={null}
      />
    )
    expect(screen.getByText('No report history for VCB yet.')).toBeInTheDocument()
  })

  it('shows upgrade arrow with correct aria-label', () => {
    render(<HistoryTimeline {...defaultProps} />)
    const arrow = screen.getByLabelText('Upgraded from Neutral to Favorable')
    expect(arrow).toBeInTheDocument()
  })

  it('shows downgrade arrow with correct aria-label', () => {
    const items = [
      makeItem(2, 'Avoid', 'Avoid now.', '2024-02-01T10:00:00Z'),
      makeItem(1, 'Neutral', 'Was neutral.', '2024-01-01T10:00:00Z'),
    ]
    render(<HistoryTimeline {...defaultProps} items={items} activeReportId={2} />)
    expect(screen.getByLabelText('Downgraded from Neutral to Avoid')).toBeInTheDocument()
  })

  it('shows 3 skeleton rows when loading and items is empty', () => {
    render(
      <HistoryTimeline
        {...defaultProps}
        items={[]}
        loading={true}
        activeReportId={null}
      />
    )
    // Should show skeleton rows, not empty state
    expect(screen.queryByText('No report history for VCB yet.')).not.toBeInTheDocument()
    // The heading still appears
    expect(screen.getByText('Report History')).toBeInTheDocument()
  })
})
