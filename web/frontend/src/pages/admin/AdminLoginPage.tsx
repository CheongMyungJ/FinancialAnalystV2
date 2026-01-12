import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiPost } from '../../lib/api'

export function AdminLoginPage() {
  const nav = useNavigate()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onLogin() {
    // GitHub Pages/static mode does not have a backend API.
    if (import.meta.env.VITE_DATA_MODE === 'static') {
      nav('/admin/factors')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await apiPost('/api/admin/auth/login', { username, password })
      nav('/admin/factors')
    } catch (e: any) {
      setError(String(e?.message ?? e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card" style={{ maxWidth: 520, margin: '0 auto' }}>
      <div className="cardHeader">
        <div>
          <div className="h3">관리자 로그인</div>
          <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
            {import.meta.env.VITE_DATA_MODE === 'static' ? (
              <span>
                GitHub Pages(정적) 모드에서는 백엔드가 없어서 로그인 기능을 사용할 수 없습니다.
              </span>
            ) : (
              <span>
                개발 기본값: <code>admin/admin</code> · 운영에서는 환경변수로 변경하세요.
              </span>
            )}
          </div>
        </div>
      </div>
      <div className="cardBody">
        {import.meta.env.VITE_DATA_MODE === 'static' ? (
          <div style={{ display: 'grid', gap: 10 }}>
            <div className="muted2" style={{ fontSize: 13 }}>
              데이터 갱신은 GitHub Actions에서 <b>Generate data (manual)</b> 워크플로를 실행해서 처리합니다.
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <a
                className="btn btnPrimary"
                href={`https://github.com/${import.meta.env.VITE_GITHUB_REPO ?? 'CheongMyungJ/FinancialAnalystV2'}/actions/workflows/generate-data.yml`}
                target="_blank"
                rel="noreferrer"
              >
                GitHub Actions로 이동
              </a>
              <button className="btn btnGhost" type="button" onClick={() => nav('/admin/factors')}>
                관리자 안내 보기
              </button>
            </div>
          </div>
        ) : (
        <div className="fieldGrid">
          <label>
            <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
              아이디
            </div>
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} />
          </label>
          <label>
            <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
              비밀번호
            </div>
            <input
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
            />
          </label>
        </div>

        <div style={{ display: 'flex', gap: 10, marginTop: 12, alignItems: 'center' }}>
          <button onClick={onLogin} disabled={loading} className="btn btnPrimary" type="button">
            {loading ? '로그인 중…' : '로그인'}
          </button>
          {error ? <span className="error">{error}</span> : <span className="muted2">쿠키 기반(JWT) 인증</span>}
        </div>
        )}
      </div>
    </div>
  )
}

