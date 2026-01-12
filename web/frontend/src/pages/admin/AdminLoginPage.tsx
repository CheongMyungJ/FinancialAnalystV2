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
            개발 기본값: <code>admin/admin</code> · 운영에서는 환경변수로 변경하세요.
          </div>
        </div>
      </div>
      <div className="cardBody">
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
      </div>
    </div>
  )
}

