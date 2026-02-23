import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Alerts from '../views/Alerts.vue'
import StockDetail from '../views/StockDetail.vue'
import BacktestView from '../views/BacktestView.vue'

const routes = [
  { path: '/', component: Dashboard },
  { path: '/alerts', component: Alerts },
  { path: '/stocks/:symbol', component: StockDetail },
  { path: '/backtest', component: BacktestView }
]

export default createRouter({
  history: createWebHistory(),
  routes
})
