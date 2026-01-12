import { Link, Navigate, Route, Routes } from 'react-router-dom'
import { AdminLoginPage } from './pages/admin/AdminLoginPage'
import { FactorsPage } from './pages/admin/FactorsPage'
import { ComparePage } from './pages/ComparePage'
import { RankingPage } from './pages/RankingPage'
import { StockDetailPage } from './pages/StockDetailPage'

export default function App() {
  return (
    <div className="appShell">
      <header className="topbar">
        <div className="topbarInner">
          <Link to="/" className="brand">
            <div className="brandMark" />
            <div>
              <div className="brandTitle">Stock Ranking</div>
              <div className="brandSub">KR/US 멀티팩터 랭킹 · 일봉 기준</div>
            </div>
          </Link>
          <nav className="nav">
            <Link className="navLink" to="/">
              랭킹
            </Link>
            <Link className="navLink" to="/admin/login">
              관리자
            </Link>
          </nav>
        </div>
      </header>

      <main className="container">
        <Routes>
          <Route path="/" element={<RankingPage />} />
          <Route path="/stocks/:market/:symbol" element={<StockDetailPage />} />
          <Route path="/compare/:market" element={<ComparePage />} />
          <Route path="/admin/login" element={<AdminLoginPage />} />
          <Route path="/admin/factors" element={<FactorsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
