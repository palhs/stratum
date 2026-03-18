export interface WatchlistItem {
  symbol: string
  name: string
  asset_type: 'equity' | 'gold_etf'
}

export interface WatchlistResponse {
  tickers: WatchlistItem[]
}

export interface WatchlistUpdate {
  tickers: string[]
}

export interface OHLCVPoint {
  time: number
  close: number
  open?: number | null
  high?: number | null
  low?: number | null
  volume?: number | null
  ma50?: number | null
  ma200?: number | null
}

export interface OHLCVResponse {
  symbol: string
  data: OHLCVPoint[]
}

export interface ReportHistoryItem {
  report_id: number
  generated_at: string
  tier: 'Favorable' | 'Neutral' | 'Cautious' | 'Avoid'
  verdict: string
}

export interface ReportHistoryResponse {
  symbol: string
  page: number
  per_page: number
  total: number
  items: ReportHistoryItem[]
}

export interface TickerData {
  symbol: string
  name: string
  asset_type: 'equity' | 'gold_etf'
  ohlcv: OHLCVPoint[] | null
  lastReport: { tier: string; generated_at: string } | null
}
