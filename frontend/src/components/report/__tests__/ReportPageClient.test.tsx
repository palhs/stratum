import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock next/dynamic to return the component synchronously
vi.mock('next/dynamic', () => ({
  default: (loader: () => Promise<{ default: React.ComponentType<unknown> }>) => {
    // Return a placeholder component for testing
    const MockDynamic = (props: Record<string, unknown>) => <div data-testid="tradingview-chart" {...props} />
    return MockDynamic
  },
}))

// Mock next/link
vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}))

// Hoist API mocks so they can be referenced in vi.mock
const { mockGetOhlcv, mockGetReportHistory, mockGetReportContent } = vi.hoisted(() => {
  const mockGetOhlcv = vi.fn()
  const mockGetReportHistory = vi.fn()
  const mockGetReportContent = vi.fn()
  return { mockGetOhlcv, mockGetReportHistory, mockGetReportContent }
})

vi.mock('@/lib/api', () => ({
  getOhlcv: mockGetOhlcv,
  getReportHistory: mockGetReportHistory,
  getReportContent: mockGetReportContent,
}))

import { ReportPageClient } from '../ReportPageClient'

const mockHistory = {
  symbol: 'VCB',
  page: 1,
  per_page: 10,
  total: 2,
  items: [
    {
      report_id: 2,
      generated_at: '2024-02-01T10:00:00Z',
      tier: 'Favorable' as const,
      verdict: 'Strong entry quality.',
    },
    {
      report_id: 1,
      generated_at: '2024-01-01T10:00:00Z',
      tier: 'Neutral' as const,
      verdict: 'Sideways consolidation.',
    },
  ],
}

const mockContent = {
  report_id: 2,
  generated_at: '2024-02-01T10:00:00Z',
  tier: 'Favorable',
  verdict: 'Strong entry quality.',
  macro_assessment: 'Positive',
  valuation_assessment: 'Fair',
  structure_assessment: 'Uptrend',
  report_markdown_vi: '# Báo cáo VN tiếng Việt',
  report_markdown_en: '# English Report Content',
}

const mockOhlcv = {
  symbol: 'VCB',
  data: [{ time: 1700000000, close: 100, open: 99, high: 102, low: 98 }],
}

describe('ReportPageClient', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetOhlcv.mockResolvedValue(mockOhlcv)
    mockGetReportHistory.mockResolvedValue(mockHistory)
    mockGetReportContent.mockResolvedValue(mockContent)
    // Clear localStorage between tests
    localStorage.clear()
  })

  it('shows loading skeleton on initial load', () => {
    // Make APIs hang
    mockGetReportHistory.mockReturnValue(new Promise(() => {}))
    render(<ReportPageClient symbol="VCB" accessToken="test-token" />)
    // Symbol heading should appear before loading resolves
    expect(screen.getByText('VCB')).toBeInTheDocument()
  })

  it('calls getReportHistory and getReportContent on mount', async () => {
    render(<ReportPageClient symbol="VCB" accessToken="test-token" />)
    await waitFor(() => {
      expect(mockGetReportHistory).toHaveBeenCalledWith('VCB', 'test-token', 1, 10)
      expect(mockGetReportContent).toHaveBeenCalledWith(2, 'test-token')
    })
  })

  it('calls getOhlcv on mount', async () => {
    render(<ReportPageClient symbol="VCB" accessToken="test-token" />)
    await waitFor(() => {
      expect(mockGetOhlcv).toHaveBeenCalledWith('VCB', 'test-token')
    })
  })

  it('shows report content after load', async () => {
    render(<ReportPageClient symbol="VCB" accessToken="test-token" />)
    await waitFor(() => {
      const matches = screen.getAllByText('Strong entry quality.')
      expect(matches.length).toBeGreaterThan(0)
    })
  })

  it('shows ReportSummaryCard with verdict after load', async () => {
    render(<ReportPageClient symbol="VCB" accessToken="test-token" />)
    await waitFor(() => {
      const verdicts = screen.getAllByText('Strong entry quality.')
      expect(verdicts.length).toBeGreaterThan(0)
      const favorables = screen.getAllByText('Favorable')
      expect(favorables.length).toBeGreaterThan(0)
    })
  })

  it('toggles ReportMarkdown visibility on expand/collapse', async () => {
    render(<ReportPageClient symbol="VCB" accessToken="test-token" />)
    await waitFor(() => {
      expect(screen.getByText('Read full report')).toBeInTheDocument()
    })

    // Markdown not visible initially
    expect(screen.queryByText('# English Report Content')).not.toBeInTheDocument()

    // Click expand
    fireEvent.click(screen.getByText('Read full report'))
    await waitFor(() => {
      expect(screen.getByText('Collapse report')).toBeInTheDocument()
    })
  })

  it('clicking history row calls getReportContent with new report_id', async () => {
    render(<ReportPageClient symbol="VCB" accessToken="test-token" />)
    await waitFor(() => {
      expect(screen.getByText('Report History')).toBeInTheDocument()
    })

    // Click on second history row (report_id=1)
    const rows = screen.getAllByRole('button')
    const historyRows = rows.filter(btn =>
      btn.textContent?.includes('Sideways consolidation.')
    )
    expect(historyRows.length).toBeGreaterThan(0)
    fireEvent.click(historyRows[0])

    await waitFor(() => {
      expect(mockGetReportContent).toHaveBeenCalledWith(1, 'test-token')
    })
  })

  it('shows error state when API fails and no report loaded', async () => {
    mockGetReportHistory.mockRejectedValue(new Error('API error'))
    render(<ReportPageClient symbol="VCB" accessToken="test-token" />)
    await waitFor(() => {
      expect(screen.getByText('No report available')).toBeInTheDocument()
    })
  })

  it('shows "Back to dashboard" link', async () => {
    render(<ReportPageClient symbol="VCB" accessToken="test-token" />)
    // Should be present in loading state too
    await waitFor(() => {
      const backLinks = screen.getAllByText('Back to dashboard')
      expect(backLinks.length).toBeGreaterThan(0)
    })
  })

  it('shows symbol heading', async () => {
    render(<ReportPageClient symbol="VCB" accessToken="test-token" />)
    await waitFor(() => {
      expect(screen.getByText('VCB')).toBeInTheDocument()
    })
  })

  it('shows "No report available" when history is empty', async () => {
    mockGetReportHistory.mockResolvedValue({
      ...mockHistory,
      items: [],
      total: 0,
    })
    render(<ReportPageClient symbol="VCB" accessToken="test-token" />)
    await waitFor(() => {
      expect(screen.getByText('No report available')).toBeInTheDocument()
    })
  })
})
