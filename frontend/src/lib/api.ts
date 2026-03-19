import type { WatchlistResponse, OHLCVResponse, ReportHistoryResponse, GenerateResponse, ReportContentResponse } from './types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

async function fetchAPI<T>(path: string, token: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function getWatchlist(token: string): Promise<WatchlistResponse> {
  return fetchAPI<WatchlistResponse>('/watchlist', token)
}

export async function getOhlcv(symbol: string, token: string): Promise<OHLCVResponse> {
  return fetchAPI<OHLCVResponse>(`/tickers/${symbol}/ohlcv`, token)
}

export async function getLastReport(symbol: string, token: string): Promise<ReportHistoryResponse> {
  return fetchAPI<ReportHistoryResponse>(`/reports/by-ticker/${symbol}?page=1&per_page=1`, token)
}

export async function addTickerToWatchlist(
  currentTickers: string[],
  newTicker: string,
  token: string
): Promise<void> {
  await fetch(`${API_BASE}/watchlist`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ tickers: [...currentTickers, newTicker] }),
  })
}

export async function generateReport(
  ticker: string,
  assetType: string,
  token: string
): Promise<GenerateResponse> {
  return fetchAPI<GenerateResponse>('/reports/generate', token, {
    method: 'POST',
    body: JSON.stringify({ ticker, asset_type: assetType }),
  })
}

export async function getReportHistory(
  symbol: string,
  token: string,
  page: number = 1,
  perPage: number = 10
): Promise<ReportHistoryResponse> {
  return fetchAPI<ReportHistoryResponse>(
    `/reports/by-ticker/${symbol}?page=${page}&per_page=${perPage}`,
    token
  )
}

export async function getReportContent(
  reportId: number,
  token: string
): Promise<ReportContentResponse> {
  return fetchAPI<ReportContentResponse>(`/reports/by-report-id/${reportId}`, token)
}
