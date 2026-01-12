import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiGet } from '../lib/api'

type Market = 'KR' | 'US'

export function RankingPage() {
  const nav = useNavigate()
  const [market, setMarket] = useState<Market>('KR')
  const [apiStatus, setApiStatus] = useState<string>('loading')
  const [items, setItems] = useState<
    Array<{
      rank: number
      delta_rank?: number | null
      grade: string
      total_score: number
      symbol: string
      name: string | null
      factor_scores?: Record<string, number | null>
    }>
  >([])
  const [query, setQuery] = useState<string>('')
  const [asofDay, setAsofDay] = useState<string | null>(null)
  const [prevDay, setPrevDay] = useState<string | null>(null)
  const [computedAt, setComputedAt] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<'rank' | 'delta' | 'total' | 'news' | 'per' | 'roe'>('rank')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [minFundFactors, setMinFundFactors] = useState<number>(0)
  const [selected, setSelected] = useState<Record<string, boolean>>({})

  useEffect(() => {
    let cancelled = false
    if (import.meta.env.VITE_DATA_MODE === 'static') {
      setApiStatus('static')
      return () => {
        cancelled = true
      }
    }
    apiGet<{ status: string }>('/api/public/health')
      .then((r) => {
        if (!cancelled) setApiStatus(r.status)
      })
      .catch(() => {
        if (!cancelled) setApiStatus('down')
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    setError(null)
    const load = async () => {
      if (import.meta.env.VITE_DATA_MODE === 'static') {
        const url = `${import.meta.env.BASE_URL}data/rankings_${market}.json`
        const res = await fetch(url, { cache: 'no-store' })
        if (!res.ok) throw new Error(`GET /data/rankings_${market}.json failed: ${res.status}`)
        const r = (await res.json()) as {
          market: Market
          day: string
          prev_day?: string | null
          computed_at: string | null
          factors: string[]
          items: Array<any>
        }
        if (cancelled) return
        setItems(r.items)
        setAsofDay(r.day)
        setPrevDay(r.prev_day ?? null)
        setComputedAt(r.computed_at)
        return
      }

      const r = await apiGet<{
        market: Market
        day: string
        prev_day?: string | null
        computed_at: string | null
        factors: string[]
        items: Array<any>
      }>(`/api/public/rankings/${market}?include_delta=1`)
      if (cancelled) return
      setItems(r.items)
      setAsofDay(r.day)
      setPrevDay(r.prev_day ?? null)
      setComputedAt(r.computed_at)
    }

    load().catch((e) => {
      if (cancelled) return
      // Static/Pages mode: if data file is missing, show a friendly guide.
      const msg = String(e?.message ?? e)
      if (import.meta.env.VITE_DATA_MODE === 'static' && msg.includes('rankings_') && msg.includes('404')) {
        setError(
          '랭킹 데이터(JSON)가 아직 생성되지 않았습니다. 관리자 메뉴에서 “GitHub Actions에서 데이터 생성 실행”을 눌러 워크플로를 한 번 실행한 뒤 새로고침 해주세요.',
        )
      } else {
        setError(msg)
      }
      setItems([])
      setAsofDay(null)
      setPrevDay(null)
      setComputedAt(null)
    })
    return () => {
      cancelled = true
    }
  }, [market])

  function badgeClass(grade: string) {
    if (grade === 'A') return 'badge badgeA'
    if (grade === 'B') return 'badge badgeB'
    if (grade === 'C') return 'badge badgeC'
    if (grade === 'D') return 'badge badgeD'
    if (grade === 'F') return 'badge badgeF'
    return 'badge'
  }

  const q = query.trim().toLowerCase()
  const filtered = useMemo(() => {
    const base0 = q
      ? items.filter((it) => {
          const sym = String(it.symbol ?? '').toLowerCase()
          const name = String(it.name ?? '').toLowerCase()
          return sym.includes(q) || name.includes(q)
        })
      : items

    const fundKeys = [
      'pe_ratio',
      'roe_ttm',
      'ev_to_ebitda',
      'fcf_yield',
      'debt_to_ebitda',
      'revenue_growth_yoy',
      'earnings_growth_yoy',
    ] as const
    const base =
      minFundFactors > 0
        ? base0.filter((it) => {
            const fs = it.factor_scores ?? {}
            const cnt = fundKeys.reduce((acc, k) => acc + (fs[k] != null ? 1 : 0), 0)
            return cnt >= minFundFactors
          })
        : base0

    const dir = sortDir === 'asc' ? 1 : -1
    const getV = (it: any) => {
      if (sortKey === 'rank') return Number(it.rank ?? 0)
      if (sortKey === 'delta') return Number(it.delta_rank ?? -999999)
      if (sortKey === 'total') return Number(it.total_score ?? 0)
      if (sortKey === 'news') return Number(it.factor_scores?.gdelt_tone ?? -999999)
      if (sortKey === 'per') return Number(it.factor_scores?.pe_ratio ?? -999999)
      if (sortKey === 'roe') return Number(it.factor_scores?.roe_ttm ?? -999999)
      return 0
    }
    return [...base].sort((a, b) => {
      const av = getV(a)
      const bv = getV(b)
      if (av === bv) return 0
      return av < bv ? -1 * dir : 1 * dir
    })
  }, [items, q, sortKey, sortDir, minFundFactors])

  const coverage = useMemo(() => {
    const total = items.length || 0
    const cnt = (k: 'gdelt_tone' | 'pe_ratio' | 'roe_ttm') =>
      items.reduce((acc, it) => acc + (it.factor_scores && it.factor_scores[k] != null ? 1 : 0), 0)
    return {
      total,
      shown: filtered.length,
      news: total ? Math.round((cnt('gdelt_tone') / total) * 100) : 0,
      per: total ? Math.round((cnt('pe_ratio') / total) * 100) : 0,
      roe: total ? Math.round((cnt('roe_ttm') / total) * 100) : 0,
    }
  }, [items, filtered.length])

  const selectedSymbols = useMemo(() => {
    return Object.entries(selected)
      .filter(([, v]) => v)
      .map(([k]) => k)
      .slice(0, 5)
  }, [selected])

  function toggleSelected(sym: string, next: boolean) {
    setSelected((prev) => ({ ...prev, [sym]: next }))
  }

  function clearSelected() {
    setSelected({})
  }

  function toggleSort(next: typeof sortKey, defaultDir: typeof sortDir) {
    if (sortKey !== next) {
      setSortKey(next)
      setSortDir(defaultDir)
      return
    }
    setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
  }

  function fmtScore(v: unknown) {
    if (v == null) return '-'
    const n = Number(v)
    return Number.isFinite(n) ? n.toFixed(1) : '-'
  }

  function avgScore(fs: Record<string, number | null> | undefined, keys: string[]) {
    if (!fs) return null
    const vals = keys.map((k) => fs[k]).filter((v) => v != null && Number.isFinite(Number(v))) as number[]
    if (vals.length === 0) return null
    return vals.reduce((a, b) => a + b, 0) / vals.length
  }

  function qvgBadge(label: string, v: number | null) {
    if (v == null) return <span className="miniPill">{label}: -</span>
    const cls = v >= 67 ? 'miniPill miniPillOk' : v >= 50 ? 'miniPill miniPillWarn' : 'miniPill'
    return (
      <span className={cls}>
        {label}: {v.toFixed(0)}
      </span>
    )
  }

  function riskBadge(atrScore: number | null) {
    if (atrScore == null) return <span className="miniPill">Risk: -</span>
    if (atrScore >= 67) return <span className="miniPill miniPillOk">Risk: Low</span>
    if (atrScore <= 33) return <span className="miniPill miniPillWarn">Risk: High</span>
    return <span className="miniPill">Risk: Med</span>
  }

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <div className="card">
        <div className="cardHeader">
          <div style={{ width: '100%' }}>
            <div className="pageHeader">
              <div>
                <div className="h3">랭킹</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                  데이터: 일봉 · 기준일: {asofDay ?? '-'} · 계산시각: {computedAt ?? '-'} · 변동 기준: {prevDay ?? '없음'}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                <span className={`miniPill ${apiStatus === 'ok' ? 'miniPillOk' : 'miniPillWarn'}`}>API: {apiStatus}</span>
                <Link to="/admin/login" className="btn btnGhost">
                  관리자
                </Link>
              </div>
            </div>

            <div className="kpiMiniGrid">
              <div className="kpiMini">
                <div className="kpiMiniLabel">시장</div>
                <div className="kpiMiniValue">{market}</div>
              </div>
              <div className="kpiMini">
                <div className="kpiMiniLabel">표시/전체</div>
                <div className="kpiMiniValue">
                  {coverage.shown} / {coverage.total}
                </div>
              </div>
              <div className="kpiMini">
                <div className="kpiMiniLabel">커버리지(뉴스)</div>
                <div className="kpiMiniValue">{coverage.news}%</div>
              </div>
              <div className="kpiMini">
                <div className="kpiMiniLabel">커버리지(재무)</div>
                <div className="kpiMiniValue">
                  PER {coverage.per}% · ROE {coverage.roe}%
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="cardBody">
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'space-between' }}>
            <div className="tabs" aria-label="market tabs">
              <button className={`tab ${market === 'KR' ? 'tabActive' : ''}`} onClick={() => setMarket('KR')} type="button">
                한국 (KR)
              </button>
              <button className={`tab ${market === 'US' ? 'tabActive' : ''}`} onClick={() => setMarket('US')} type="button">
                미국 (US)
              </button>
            </div>

            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
              <button
                className="btn btnGhost"
                type="button"
                disabled={selectedSymbols.length < 2}
                onClick={() => {
                  const qs = encodeURIComponent(selectedSymbols.join(','))
                  nav(`/compare/${market}?symbols=${qs}`)
                }}
                title="2~5개 선택 후 비교"
              >
                비교 ({selectedSymbols.length})
              </button>
              <button className="btn btnGhost" type="button" disabled={selectedSymbols.length === 0} onClick={clearSelected}>
                선택 해제
              </button>
                <select
                  className="select"
                  value={minFundFactors}
                  onChange={(e) => setMinFundFactors(Number(e.target.value))}
                  style={{ width: 210 }}
                >
                  <option value={0}>재무 커버리지: 전체</option>
                  <option value={2}>재무 커버리지: 2개 이상</option>
                  <option value={4}>재무 커버리지: 4개 이상</option>
                  <option value={6}>재무 커버리지: 6개 이상</option>
                </select>
              <input
                className="input"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="종목명 또는 티커로 검색 (예: 005930, AAPL)"
                style={{ width: 340, maxWidth: '70vw' }}
              />
            </div>
          </div>

          <div className="tableWrap" style={{ marginTop: 12 }}>
            <table className="table">
              <thead>
                <tr>
                  <th className="th" style={{ width: 56 }} />
                  <th className="th" style={{ textAlign: 'right', width: 70 }}>
                    <span className="sortBtn" onClick={() => toggleSort('rank', 'asc')}>
                      순위 {sortKey === 'rank' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                    </span>
                  </th>
                  <th className="th" style={{ textAlign: 'right', width: 80 }}>
                    <span className="sortBtn" onClick={() => toggleSort('delta', 'desc')}>
                      변동 {sortKey === 'delta' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                    </span>
                  </th>
                  <th className="th">종목</th>
                  <th className="th" style={{ width: 110 }}>
                    티커
                  </th>
                  <th className="th" style={{ width: 220 }}>
                    중장기 요약
                  </th>
                  <th className="th" style={{ textAlign: 'right', width: 90 }}>
                    <span className="sortBtn" onClick={() => toggleSort('news', 'desc')}>
                      뉴스톤 {sortKey === 'news' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                    </span>
                  </th>
                  <th className="th" style={{ textAlign: 'right', width: 80 }}>
                    <span className="sortBtn" onClick={() => toggleSort('per', 'asc')}>
                      PER {sortKey === 'per' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                    </span>
                  </th>
                  <th className="th" style={{ textAlign: 'right', width: 90 }}>
                    <span className="sortBtn" onClick={() => toggleSort('roe', 'desc')}>
                      ROE {sortKey === 'roe' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                    </span>
                  </th>
                  <th className="th" style={{ textAlign: 'right', width: 140 }}>
                    <span className="sortBtn" onClick={() => toggleSort('total', 'desc')}>
                      총점 {sortKey === 'total' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                    </span>
                  </th>
                  <th className="th" style={{ textAlign: 'center', width: 90 }}>
                    등급
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => (
                  <tr key={`${market}:${s.symbol}`} className="trHover">
                    <td className="td">
                      <input
                        type="checkbox"
                        checked={Boolean(selected[s.symbol])}
                        onChange={(e) => toggleSelected(s.symbol, e.target.checked)}
                        disabled={!selected[s.symbol] && selectedSymbols.length >= 5}
                        title="비교에 추가(최대 5개)"
                      />
                    </td>
                    <td className="td" style={{ textAlign: 'right' }}>
                      {s.rank}
                    </td>
                    <td className="td" style={{ textAlign: 'right' }}>
                      {s.delta_rank == null ? (
                        <span className="muted2">-</span>
                      ) : Number(s.delta_rank) > 0 ? (
                        <span className="pill scorePillPos">+{s.delta_rank}</span>
                      ) : Number(s.delta_rank) < 0 ? (
                        <span className="pill scorePillNeg">{s.delta_rank}</span>
                      ) : (
                        <span className="pill scorePillNeu">0</span>
                      )}
                    </td>
                    <td className="td">
                      <Link to={`/stocks/${market}/${s.symbol}`}>{s.name ?? s.symbol}</Link>
                      <div className="muted2" style={{ fontSize: 12, marginTop: 2 }}>
                        <span className="mono">{s.symbol}</span>
                      </div>
                    </td>
                    <td className="td">{s.symbol}</td>
                    <td className="td">
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {qvgBadge('Q', avgScore(s.factor_scores, ['roe_ttm', 'debt_to_ebitda']))}
                        {qvgBadge('V', avgScore(s.factor_scores, ['ev_to_ebitda', 'fcf_yield', 'pe_ratio']))}
                        {qvgBadge('G', avgScore(s.factor_scores, ['revenue_growth_yoy', 'earnings_growth_yoy']))}
                        {riskBadge((s.factor_scores?.atr_14p as any) ?? null)}
                      </div>
                      <div className="muted2" style={{ fontSize: 12, marginTop: 4 }}>
                        RS: {fmtScore(s.factor_scores?.rs_6m_vs_benchmark)}
                      </div>
                    </td>
                    <td className="td" style={{ textAlign: 'right' }}>
                      {fmtScore(s.factor_scores?.gdelt_tone)}
                    </td>
                    <td className="td" style={{ textAlign: 'right' }}>
                      {fmtScore(s.factor_scores?.pe_ratio)}
                    </td>
                    <td className="td" style={{ textAlign: 'right' }}>
                      {fmtScore(s.factor_scores?.roe_ttm)}
                    </td>
                    <td className="td" style={{ textAlign: 'right' }}>
                      {Number.isFinite(s.total_score) ? s.total_score.toFixed(2) : '-'}
                    </td>
                    <td className="td" style={{ textAlign: 'center' }}>
                      <span className={badgeClass(s.grade)}>{s.grade}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {error ? <p className="error" style={{ marginTop: 12 }}>{error}</p> : null}

          {!error ? (
            <div className="muted2" style={{ marginTop: 12, fontSize: 12, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <span>정렬/검색은 프론트에서 처리됩니다(표시 데이터 기준).</span>
              <span>
                총점 = Σ(팩터점수×가중치) / Σ(가중치). 결측(점수 없음) 팩터는 자동 제외됩니다.
              </span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

