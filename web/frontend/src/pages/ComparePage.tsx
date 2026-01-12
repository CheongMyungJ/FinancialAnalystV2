import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { apiGet } from '../lib/api'

type Market = 'KR' | 'US'

type StockDetail = {
  market: Market
  symbol: string
  name: string | null
  day: string
  computed_at: string | null
  ranking: { rank: number | null; grade: string | null; total_score: number | null } | null
  breakdown: Array<{
    key: string
    name: string
    factor_type: string
    weight: number
    raw_value: number | null
    score: number | null
    enabled: boolean
  }>
}

type PriceBars = { bars: Array<{ date: string; close: number }> }

function fmtPct(v: number | null) {
  if (v == null) return '-'
  const n = Number(v) * 100
  if (!Number.isFinite(n)) return '-'
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}%`
}

function computeKpis(prices: Array<{ close: number }> | null) {
  const ps = prices ?? []
  if (ps.length < 30) return null
  const closes = ps.map((p) => Number(p.close)).filter((x) => Number.isFinite(x))
  if (closes.length < 30) return null
  const last = closes[closes.length - 1]
  const retFrom = (idxBack: number) => {
    if (closes.length <= idxBack) return null
    const base = closes[closes.length - 1 - idxBack]
    if (!Number.isFinite(base) || base <= 0) return null
    return (last / base) - 1
  }
  const ret1m = retFrom(21)
  const ret1y = retFrom(252)
  const ret3y = retFrom(252 * 3)

  let peak = closes[0]
  let mdd = 0
  for (const c of closes) {
    if (c > peak) peak = c
    const dd = peak > 0 ? c / peak - 1 : 0
    if (dd < mdd) mdd = dd
  }

  const rets: number[] = []
  for (let i = 1; i < closes.length; i++) {
    const a = closes[i - 1]
    const b = closes[i]
    if (a > 0) rets.push(b / a - 1)
  }
  const mean = rets.reduce((a, b) => a + b, 0) / Math.max(1, rets.length)
  const var_ = rets.reduce((a, r) => a + (r - mean) * (r - mean), 0) / Math.max(1, rets.length - 1)
  const vol = Math.sqrt(Math.max(0, var_)) * Math.sqrt(252)

  return { last, ret1m, ret1y, ret3y, mdd, vol }
}

export function ComparePage() {
  const { market } = useParams()
  const nav = useNavigate()
  const [sp] = useSearchParams()
  const mkt = (market ?? 'KR').toUpperCase() as Market
  const symbols = (sp.get('symbols') ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 5)

  const [details, setDetails] = useState<Record<string, StockDetail | null>>({})
  const [prices, setPrices] = useState<Record<string, Array<{ date: string; close: number }> | null>>({})
  const [error, setError] = useState<string | null>(null)
  const [factorView, setFactorView] = useState<'core' | 'all'>('core')

  useEffect(() => {
    let cancelled = false
    setError(null)
    if (symbols.length < 2) {
      setError('비교는 최소 2개 종목을 선택해야 합니다.')
      return
    }
    ;(async () => {
      try {
        const outD: Record<string, StockDetail | null> = {}
        const outP: Record<string, Array<{ date: string; close: number }> | null> = {}
        for (const sym of symbols) {
          // detail
          outD[sym] = await apiGet<StockDetail>(`/api/public/stocks/${mkt}/${sym}`)
          // prices (long window for KPIs)
          const pb = await apiGet<PriceBars>(`/api/public/stocks/${mkt}/${sym}/prices?limit=900`)
          outP[sym] = pb.bars.map((b) => ({ date: b.date, close: Number(b.close) }))
        }
        if (cancelled) return
        setDetails(outD)
        setPrices(outP)
      } catch (e: any) {
        if (cancelled) return
        setError(String(e?.message ?? e))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [mkt, symbols.join(',')])

  const commonFactors = useMemo(() => {
    const ds = symbols.map((s) => details[s]).filter(Boolean) as StockDetail[]
    if (ds.length < 2) return []
    const enabledSets = ds.map((d) => new Set(d.breakdown.filter((b) => b.enabled).map((b) => b.key)))
    const inter = new Set<string>(enabledSets[0])
    for (const s of enabledSets.slice(1)) for (const k of [...inter]) if (!s.has(k)) inter.delete(k)
    // keep a curated order for long-term view
    const preferred = [
      'gdelt_tone',
      'news_tone_change',
      'news_volume_14d',
      'atr_14p',
      'rs_6m_vs_benchmark',
      'pe_ratio',
      'roe_ttm',
      'ev_to_ebitda',
      'fcf_yield',
      'debt_to_ebitda',
      'revenue_growth_yoy',
      'earnings_growth_yoy',
    ]
    const out = preferred.filter((k) => inter.has(k))
    // plus any other enabled factors common
    const rest = [...inter].filter((k) => !out.includes(k)).sort()
    return [...out, ...rest]
  }, [details, symbols.join(',')])

  const coreKeys = useMemo(() => {
    // Core long-term view: Q/V/G + Risk + RS + (optional) news change
    return [
      'roe_ttm',
      'debt_to_ebitda',
      'ev_to_ebitda',
      'fcf_yield',
      'pe_ratio',
      'revenue_growth_yoy',
      'earnings_growth_yoy',
      'atr_14p',
      'rs_6m_vs_benchmark',
      'news_tone_change',
    ]
  }, [])

  const shownFactors = useMemo(() => {
    if (factorView === 'all') return commonFactors
    const s = new Set(commonFactors)
    return coreKeys.filter((k) => s.has(k))
  }, [factorView, commonFactors, coreKeys])

  const factorMeta = useMemo(() => {
    const first = (details[symbols[0]]?.breakdown ?? []) as any[]
    const m: Record<string, { name: string; factor_type: string }> = {}
    for (const b of first) m[b.key] = { name: b.name, factor_type: b.factor_type }
    return m
  }, [details, symbols.join(',')])

  function getScore(sym: string, key: string) {
    const b = (details[sym]?.breakdown ?? []).find((x) => x.key === key)
    const v = b?.score
    if (v == null) return null
    const n = Number(v)
    return Number.isFinite(n) ? n : null
  }

  function avgScore(sym: string, keys: string[]) {
    const vals = keys.map((k) => getScore(sym, k)).filter((v) => v != null) as number[]
    if (vals.length === 0) return null
    return vals.reduce((a, b) => a + b, 0) / vals.length
  }

  function badge(label: string, v: number | null) {
    if (v == null) return <span className="miniPill">{label}: -</span>
    const cls = v >= 67 ? 'miniPill miniPillOk' : v >= 50 ? 'miniPill miniPillWarn' : 'miniPill'
    return (
      <span className={cls}>
        {label}: {v.toFixed(0)}
      </span>
    )
  }

  function riskPill(v: number | null) {
    // atr_14p 점수는 "낮을수록 좋은 raw"를 백분위로 변환한 값이라,
    // 점수가 높을수록(=ATR 낮을수록) 리스크가 낮다고 해석 가능.
    if (v == null) return <span className="miniPill">Risk: -</span>
    if (v >= 67) return <span className="miniPill miniPillOk">Risk: Low</span>
    if (v <= 33) return <span className="miniPill miniPillWarn">Risk: High</span>
    return <span className="miniPill">Risk: Med</span>
  }

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <div className="card">
        <div className="cardHeader">
          <div>
            <div className="h3">종목 비교</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
              {mkt} · {symbols.join(', ') || '-'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <Link to="/" className="btn btnGhost">
              ← 랭킹
            </Link>
            <button className="btn" type="button" onClick={() => nav('/')}>
              완료
            </button>
          </div>
        </div>
        <div className="cardBody">
          {error ? <p className="error">{error}</p> : null}
          {!error ? (
            <div className="muted2" style={{ fontSize: 12 }}>
              팩터 점수는 0~100(시장 내 백분위) 기준입니다. KPI는 가격 데이터 기반(가능 범위 내)입니다.
            </div>
          ) : null}
        </div>
      </div>

      <div className="card">
        <div className="cardHeader">
          <div className="h3">요약 비교</div>
        </div>
        <div className="cardBody">
          <div className="tableWrap">
            <table className="table">
              <thead>
                <tr>
                  <th className="th" style={{ width: 220 }}>
                    항목
                  </th>
                  {symbols.map((s) => (
                    <th key={s} className="th">
                      <Link to={`/stocks/${mkt}/${s}`}>{details[s]?.name ?? s}</Link>
                      <div className="muted2" style={{ fontSize: 12, marginTop: 2 }}>
                        <span className="mono">{s}</span>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  { key: 'total', label: '총점', get: (d: StockDetail) => (d.ranking?.total_score != null ? d.ranking.total_score.toFixed(2) : '-') },
                  { key: 'grade', label: '등급/순위', get: (d: StockDetail) => `${d.ranking?.grade ?? '-'} / ${d.ranking?.rank ?? '-'}` },
                  {
                    key: 'price',
                    label: '최근 종가(대략)',
                    get: (_: StockDetail, sym: string) => {
                      const k = computeKpis(prices[sym])
                      return k?.last != null ? k.last.toFixed(2) : '-'
                    },
                  },
                  { key: 'r1m', label: '1M 수익률', get: (_: StockDetail, sym: string) => fmtPct(computeKpis(prices[sym])?.ret1m ?? null) },
                  { key: 'r1y', label: '1Y 수익률', get: (_: StockDetail, sym: string) => fmtPct(computeKpis(prices[sym])?.ret1y ?? null) },
                  { key: 'r3y', label: '3Y 수익률', get: (_: StockDetail, sym: string) => fmtPct(computeKpis(prices[sym])?.ret3y ?? null) },
                  { key: 'mdd', label: '최대낙폭(MDD)', get: (_: StockDetail, sym: string) => fmtPct(computeKpis(prices[sym])?.mdd ?? null) },
                  { key: 'vol', label: '변동성(연환산)', get: (_: StockDetail, sym: string) => fmtPct(computeKpis(prices[sym])?.vol ?? null) },
                ].map((row) => (
                  <tr key={row.key} className="trHover">
                    <td className="td" style={{ fontWeight: 800 }}>
                      {row.label}
                    </td>
                    {symbols.map((s) => (
                      <td key={s} className="td">
                        {details[s] ? row.get(details[s] as StockDetail, s) : '-'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="cardHeader">
          <div>
            <div className="h3">팩터 점수 비교</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
              공통 ON 팩터 기준 · 보기: {factorView === 'core' ? '핵심(Q/V/G/Risk/RS)' : '전체'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <button className={`tab ${factorView === 'core' ? 'tabActive' : ''}`} type="button" onClick={() => setFactorView('core')}>
              핵심만
            </button>
            <button className={`tab ${factorView === 'all' ? 'tabActive' : ''}`} type="button" onClick={() => setFactorView('all')}>
              전체
            </button>
          </div>
        </div>
        <div className="cardBody">
          <div className="card" style={{ padding: 12, boxShadow: 'none', marginBottom: 12 }}>
            <div className="muted" style={{ fontSize: 12, fontWeight: 800, letterSpacing: 0.02 }}>
              핵심 프리셋 요약(Q/V/G + Risk + RS)
            </div>
            <div className="muted2" style={{ fontSize: 12, marginTop: 4 }}>
              Q=ROE/부채, V=EV·FCF·PER, G=성장, Risk=ATR, RS=상대강도(6M)
            </div>
            <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
              {symbols.map((s) => (
                <div key={s} style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                  <span className="pill mono">{s}</span>
                  {badge('Q', avgScore(s, ['roe_ttm', 'debt_to_ebitda']))}
                  {badge('V', avgScore(s, ['ev_to_ebitda', 'fcf_yield', 'pe_ratio']))}
                  {badge('G', avgScore(s, ['revenue_growth_yoy', 'earnings_growth_yoy']))}
                  {riskPill(getScore(s, 'atr_14p'))}
                  {badge('RS', getScore(s, 'rs_6m_vs_benchmark'))}
                </div>
              ))}
            </div>
          </div>

          <div className="tableWrap">
            <table className="table">
              <thead>
                <tr>
                  <th className="th" style={{ width: 260 }}>
                    팩터
                  </th>
                  {symbols.map((s) => (
                    <th key={s} className="th" style={{ textAlign: 'right' }}>
                      {s}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {shownFactors.length === 0 ? (
                  <tr>
                    <td className="td" colSpan={1 + symbols.length}>
                      <span className="muted">공통 ON 팩터가 없거나 데이터가 부족합니다.</span>
                    </td>
                  </tr>
                ) : (
                  shownFactors.map((k) => (
                    <tr key={k} className="trHover">
                      <td className="td">
                        <div style={{ fontWeight: 800 }}>{factorMeta[k]?.name ?? k}</div>
                        <div className="muted2" style={{ fontSize: 12, marginTop: 2 }}>
                          <span className="mono">{k}</span> · {factorMeta[k]?.factor_type ?? '-'}
                        </div>
                      </td>
                      {symbols.map((s) => {
                        const b = (details[s]?.breakdown ?? []).find((x) => x.key === k)
                        const v = b?.score
                        return (
                          <td key={s} className="td" style={{ textAlign: 'right' }}>
                            {v == null ? '-' : Number(v).toFixed(1)}
                          </td>
                        )
                      })}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

