import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000'
})

export const fetchMarketRegime = () => api.get('/market/regime')
export const fetchTopStocks = () => api.get('/stocks/top')
export const fetchStockDetail = (symbol) => api.get(`/stocks/${symbol}`)
export const fetchScanLatest = () => api.get('/scan/latest')
export const fetchAlerts = () => api.get('/alerts/distribution')
export const fetchPortfolio = () => api.get('/portfolio')
export const fetchBacktest = (symbol, strategy) => api.get(`/backtest/${symbol}?strategy=${strategy}`)

export default api
