import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000'
})

export const fetchMarketRegime = () => api.get('/market/regime')
export const fetchVnindexSeries = (limit = 120) => api.get(`/market/vnindex/series?limit=${limit}`)
export const fetchTopStocks = () => api.get('/stocks/top')
export const fetchStockDetail = (symbol) => api.get(`/stocks/${symbol}`)
export const fetchScanLatest = () => api.get('/scan/latest')
export const fetchAlerts = () => api.get('/alerts/distribution')
export const fetchPortfolio = () => api.get('/portfolio')
export const createPortfolioItem = (payload) => api.post('/portfolio', payload)
export const updatePortfolioItem = (symbol, payload) => api.put(`/portfolio/${symbol}`, payload)
export const deletePortfolioItem = (symbol) => api.delete(`/portfolio/${symbol}`)
export const fetchBacktest = (symbol, strategy) => api.get(`/backtest/${symbol}?strategy=${strategy}`)

export default api
