import { useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { Link, useParams } from 'react-router-dom'
import { apiGet } from '../lib/api'

export function StockDetailPage() {
  const { market, symbol } = useParams()
  const [detail, setDetail] = useState<any | null>(null)
  const [prices, setPrices] = useState<Array<{ date: string; close: number }> | null>(null)
  const [news, setNews] = useState<Array<any>>([])
  const [error, setError] = useState<string | null>(null)
  const [factorFilter, setFactorFilter] = useState<'all' | 'enabled' | 'missing'>('all')
  const [factorGroup, setFactorGroup] = useState<'type' | 'none'>('type')

  useEffect(() => {
    if (!market || !symbol) return
    let cancelled = false
    setError(null)
    apiGet(`/api/public/stocks/${market}/${symbol}`)
      .then((r) => {
        if (cancelled) return
        setDetail(r)
      })
      .catch((e) => {
        if (cancelled) return
        setError(String(e?.message ?? e))
        setDetail(null)
      })
    return () => {
      cancelled = true
    }
  }, [market, symbol])

  useEffect(() => {
    if (!market || !symbol) return
    let cancelled = false
    // Pull a longer window for long-term KPIs (1Y/3Y, MDD, vol). UI can still show the most recent window.
    apiGet<{ bars: Array<{ date: string; close: number }> }>(`/api/public/stocks/${market}/${symbol}/prices?limit=900`)
      .then((r) => {
        if (cancelled) return
        setPrices(r.bars.map((b) => ({ date: b.date, close: Number(b.close) })))
      })
      .catch(() => {
        if (cancelled) return
        setPrices(null)
      })
    return () => {
      cancelled = true
    }
  }, [market, symbol])

  useEffect(() => {
    if (!market || !symbol) return
    let cancelled = false
    apiGet<{ items: Array<any> }>(`/api/public/stocks/${market}/${symbol}/news?limit=20`)
      .then((r) => {
        if (cancelled) return
        setNews(r.items)
      })
      .catch(() => {
        if (cancelled) return
        setNews([])
      })
    return () => {
      cancelled = true
    }
  }, [market, symbol])

  const chartOption = useMemo(() => {
    const xs = (prices ?? []).map((p) => p.date)
    const ys = (prices ?? []).map((p) => p.close)
    return {
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 20, top: 20, bottom: 40 },
      xAxis: { type: 'category', data: xs, axisLabel: { hideOverlap: true } },
      yAxis: { type: 'value', scale: true },
      series: [{ type: 'line', data: ys, smooth: true, showSymbol: false }],
    }
  }, [prices])

  const latestClose = useMemo(() => {
    if (!prices || prices.length === 0) return null
    return prices[prices.length - 1].close
  }, [prices])

  const return1m = useMemo(() => {
    if (!prices || prices.length < 22) return null
    const a = prices[prices.length - 22]?.close
    const b = prices[prices.length - 1]?.close
    if (!Number.isFinite(a) || !Number.isFinite(b) || a <= 0) return null
    return (b / a) - 1
  }, [prices])

  const longKpis = useMemo(() => {
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
    const ret1y = retFrom(252)
    const ret3y = retFrom(252 * 3)

    // max drawdown over available window
    let peak = closes[0]
    let mdd = 0
    for (const c of closes) {
      if (c > peak) peak = c
      const dd = peak > 0 ? (c / peak) - 1 : 0
      if (dd < mdd) mdd = dd
    }

    // annualized volatility (daily returns std * sqrt(252))
    const rets: number[] = []
    for (let i = 1; i < closes.length; i++) {
      const a = closes[i - 1]
      const b = closes[i]
      if (a > 0) rets.push(b / a - 1)
    }
    const mean = rets.reduce((a, b) => a + b, 0) / Math.max(1, rets.length)
    const var_ = rets.reduce((a, r) => a + (r - mean) * (r - mean), 0) / Math.max(1, rets.length - 1)
    const vol = Math.sqrt(Math.max(0, var_)) * Math.sqrt(252)

    return {
      ret1y,
      ret3y,
      mdd,
      vol,
      windowDays: closes.length,
    }
  }, [prices])

  function badgeClass(grade: string) {
    if (grade === 'A') return 'badge badgeA'
    if (grade === 'B') return 'badge badgeB'
    if (grade === 'C') return 'badge badgeC'
    if (grade === 'D') return 'badge badgeD'
    if (grade === 'F') return 'badge badgeF'
    return 'badge'
  }

  function fmtPct(v: number | null) {
    if (v == null) return '-'
    const n = Number(v) * 100
    if (!Number.isFinite(n)) return '-'
    const sign = n > 0 ? '+' : ''
    return `${sign}${n.toFixed(2)}%`
  }

  function scorePillClass(score: number | null | undefined) {
    if (score == null || !Number.isFinite(score)) return 'pill scorePillNeu'
    if (score >= 67) return 'pill scorePillPos'
    if (score <= 33) return 'pill scorePillNeg'
    return 'pill scorePillNeu'
  }

  const breakdownFiltered = useMemo(() => {
    const arr = (detail?.breakdown ?? []) as Array<any>
    if (factorFilter === 'enabled') return arr.filter((b) => Boolean(b.enabled))
    if (factorFilter === 'missing') return arr.filter((b) => b.score == null)
    return arr
  }, [detail, factorFilter])

  const breakdownByType = useMemo(() => {
    const base = breakdownFiltered
    const groups: Record<string, Array<any>> = { technical: [], fundamental: [], sentiment: [], other: [] }
    for (const b of base) {
      const t = String(b.factor_type ?? 'other')
      if (t === 'technical') groups.technical.push(b)
      else if (t === 'fundamental') groups.fundamental.push(b)
      else if (t === 'sentiment') groups.sentiment.push(b)
      else groups.other.push(b)
    }
    return groups
  }, [breakdownFiltered])

  const summaryTop = useMemo(() => {
    const arr = (detail?.breakdown ?? []) as Array<any>
    if (!arr || arr.length === 0) return { top: [], den: 0, missing: 0, enabledTotal: 0 }

    const enabled = arr.filter((b) => Boolean(b.enabled))
    const present = enabled.filter((b) => b.score != null && Number.isFinite(Number(b.score)))
    const missing = enabled.length - present.length
    const den = present.reduce((acc, b) => acc + Number(b.weight || 0), 0)

    const rows = present
      .map((b) => {
        const w = Number(b.weight || 0)
        const s = Number(b.score)
        const share = den > 0 ? w / den : 0
        const contrib = share * s // "총점에서의 기여 점수" (0~100 스케일)
        return {
          key: String(b.key),
          name: String(b.name ?? b.key),
          factor_type: String(b.factor_type ?? ''),
          weight: w,
          score: s,
          share,
          contrib,
        }
      })
      .sort((a, b) => b.contrib - a.contrib)
      .slice(0, 5)

    const enabledTotal = enabled.reduce((acc, b) => acc + Number(b.weight || 0), 0)
    return { top: rows, den, missing, enabledTotal }
  }, [detail])

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <div className="card">
        <div className="cardHeader">
          <div className="detailHeader">
            <div className="breadcrumbs">
              <Link to="/" className="muted">
                랭킹
              </Link>
              <span className="muted2">/</span>
              <span className="pill pillStrong">{market ?? '-'}</span>
              <span className="pill mono">{symbol ?? '-'}</span>
            </div>
            <div className="h3" style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <span>{detail?.name ?? detail?.symbol ?? '종목 상세'}</span>
              {detail?.ranking?.grade ? <span className={badgeClass(detail.ranking.grade)}>{detail.ranking.grade}</span> : null}
              {detail?.ranking?.rank ? <span className="pill">#{detail.ranking.rank}</span> : null}
            </div>
            <div className="muted" style={{ fontSize: 12 }}>
              기준일: {detail?.day ?? '-'} · 계산시각: {detail?.computed_at ?? '-'}
            </div>
          </div>
          <Link to="/" className="btn btnGhost">
            ← 랭킹
          </Link>
        </div>
        <div className="cardBody">
          {error ? <p className="error">{error}</p> : null}
          {!detail ? (
            <p className="muted">불러오는 중…</p>
          ) : (
            <div className="kpiGrid">
              <div className="kpi">
                <div className="kpiLabel">총점</div>
                <div className="kpiValue">{detail.ranking?.total_score != null ? Number(detail.ranking.total_score).toFixed(2) : '-'}</div>
              </div>
              <div className="kpi">
                <div className="kpiLabel">등급</div>
                <div className="kpiValue">{detail.ranking?.grade ?? '-'}</div>
              </div>
              <div className="kpi">
                <div className="kpiLabel">최근 종가(대략)</div>
                <div className="kpiValue">{latestClose != null ? latestClose.toFixed(2) : '-'}</div>
              </div>
              <div className="kpi">
                <div className="kpiLabel">1개월 수익률</div>
                <div className="kpiValue">{fmtPct(return1m)}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="detailGrid">
        <div style={{ display: 'grid', gap: 14 }}>
          <div className="card">
            <div className="cardHeader">
              <div>
                <div className="h3">핵심 요약</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                  총점 기여 TOP 5 (결측 제외 후 가중치 재정규화 기준)
                </div>
              </div>
            </div>
            <div className="cardBody">
              {!detail ? (
                <p className="muted">불러오는 중…</p>
              ) : (
                <div style={{ display: 'grid', gap: 10 }}>
                  <div className="muted2" style={{ fontSize: 12, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    <span>
                      사용 가중치 합: <span className="mono">{summaryTop.den.toFixed(2)}</span> /{' '}
                      <span className="mono">{summaryTop.enabledTotal.toFixed(2)}</span>
                    </span>
                    <span>
                      결측(ON이지만 점수 없음): <span className="mono">{summaryTop.missing}</span>개
                    </span>
                    <span>
                      장기 KPI(가능한 범위):{' '}
                      <span className="mono">{longKpis ? `${longKpis.windowDays}d` : '-'}</span>
                    </span>
                  </div>

                  {summaryTop.top.length === 0 ? (
                    <p className="muted">아직 계산된 팩터 점수가 없습니다(배치 재계산 필요)</p>
                  ) : (
                    <div className="factorGroup">
                      {summaryTop.top.map((t) => {
                        const fill = Math.max(0, Math.min(100, t.score))
                        return (
                          <div key={t.key} className="factorRow" style={{ gridTemplateColumns: '1.8fr 120px 120px 1fr' }}>
                            <div>
                              <div className="factorName">{t.name}</div>
                              <div className="factorMeta">
                                <span className="mono">{t.key}</span> · {t.factor_type}
                              </div>
                            </div>

                            <div style={{ display: 'grid', gap: 6, justifyItems: 'end' }}>
                              <div className={scorePillClass(t.score)}>{t.score.toFixed(1)}</div>
                              <div className="scoreBar" title={`score ${t.score.toFixed(1)}`}>
                                <div className="scoreBarFill" style={{ width: `${fill}%` }} />
                              </div>
                            </div>

                            <div className="muted2" style={{ textAlign: 'right', fontSize: 12, lineHeight: 1.4 }}>
                              <div>
                                비중: <span className="mono">{(t.share * 100).toFixed(1)}%</span>
                              </div>
                              <div>
                                기여: <span className="mono">{t.contrib.toFixed(1)}</span>
                              </div>
                            </div>

                            <div className="muted2" style={{ fontSize: 12 }}>
                              w <span className="mono">{t.weight.toFixed(2)}</span>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <div className="cardHeader">
              <div>
                <div className="h3">중장기 KPI</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                  수익률/리스크 (가격 데이터 기반)
                </div>
              </div>
            </div>
            <div className="cardBody">
              {!longKpis ? (
                <p className="muted">가격 데이터가 부족해 KPI를 계산할 수 없습니다.</p>
              ) : (
                <div className="kpiGrid">
                  <div className="kpi">
                    <div className="kpiLabel">1Y 수익률</div>
                    <div className="kpiValue">{fmtPct(longKpis.ret1y)}</div>
                  </div>
                  <div className="kpi">
                    <div className="kpiLabel">3Y 수익률</div>
                    <div className="kpiValue">{fmtPct(longKpis.ret3y)}</div>
                  </div>
                  <div className="kpi">
                    <div className="kpiLabel">최대낙폭(MDD)</div>
                    <div className="kpiValue">{fmtPct(longKpis.mdd)}</div>
                  </div>
                  <div className="kpi">
                    <div className="kpiLabel">변동성(연환산)</div>
                    <div className="kpiValue">{fmtPct(longKpis.vol)}</div>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <div className="cardHeader">
              <div>
                <div className="h3">가격 차트(일봉)</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                  최근 260일 · 종가 기준
                </div>
              </div>
            </div>
            <div className="cardBody">
              {prices && prices.length > 0 ? (
                <ReactECharts option={chartOption} style={{ height: 340, width: '100%' }} />
              ) : (
                <p className="muted">가격 데이터가 없습니다(배치 재계산 후 다시 시도)</p>
              )}
            </div>
          </div>

          <div className="card">
            <div className="cardHeader">
              <div>
                <div className="h3">팩터 breakdown</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                  점수(0~100) · 가중치 · 결측 사유
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                <select
                  className="select"
                  value={factorFilter}
                  onChange={(e) => setFactorFilter(e.target.value as any)}
                  style={{ width: 150 }}
                >
                  <option value="all">전체</option>
                  <option value="enabled">ON만</option>
                  <option value="missing">결측만</option>
                </select>
                <select
                  className="select"
                  value={factorGroup}
                  onChange={(e) => setFactorGroup(e.target.value as any)}
                  style={{ width: 150 }}
                >
                  <option value="type">타입별</option>
                  <option value="none">그룹 없음</option>
                </select>
              </div>
            </div>
            <div className="cardBody">
              <div className="muted2" style={{ fontSize: 12, marginBottom: 10 }}>
                총점 = Σ(팩터점수×가중치) / Σ(가중치). 결측(점수 없음) 팩터는 자동 제외됩니다.
              </div>

              {detail ? (
                <div className="factorGroup">
                  {(factorGroup === 'type'
                    ? ([
                        ['technical', '기술(가격/수급)'],
                        ['fundamental', '재무(가치/성장)'],
                        ['sentiment', '뉴스/심리'],
                        ['other', '기타'],
                      ] as const)
                    : ([['all', '전체']] as const)
                  ).map(([key, label]) => {
                    const rows =
                      factorGroup === 'type'
                        ? (breakdownByType[key] ?? [])
                        : breakdownFiltered
                    if (!rows || rows.length === 0) return null
                    return (
                      <div key={key} style={{ display: 'grid', gap: 10 }}>
                        <div className="muted" style={{ fontSize: 12, fontWeight: 800, letterSpacing: 0.02 }}>
                          {label} · {rows.length}개
                        </div>
                        {rows.map((b: any) => {
                          const s = b.score == null ? null : Number(b.score)
                          const fill = s == null || !Number.isFinite(s) ? 0 : Math.max(0, Math.min(100, s))
                          return (
                            <div key={b.key} className="factorRow">
                              <div>
                                <div className="factorName">{b.name}</div>
                                <div className="factorMeta">
                                  <span className="mono">{b.key}</span> · w {Number(b.weight).toFixed(2)} · {b.enabled ? 'ON' : 'OFF'}
                                </div>
                                {b.note ? <div className="factorMeta">{b.note}</div> : null}
                              </div>

                              <div style={{ display: 'grid', gap: 6, justifyItems: 'end' }}>
                                <div className={scorePillClass(s)}>{s == null ? '-' : s.toFixed(1)}</div>
                                <div className="scoreBar" title={s == null ? '' : `score ${s.toFixed(1)}`}>
                                  <div className="scoreBarFill" style={{ width: `${fill}%` }} />
                                </div>
                              </div>

                              <div className="muted2" style={{ textAlign: 'right', fontSize: 12 }}>
                                {b.factor_type}
                              </div>

                              <div className="muted2" style={{ textAlign: 'right', fontSize: 12 }}>
                                raw: {b.raw_value == null ? '-' : String(b.raw_value)}
                              </div>

                              <div className="muted2" style={{ fontSize: 12 }}>
                                {b.higher_is_better ? '높을수록 좋음' : '낮을수록 좋음'}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <p className="muted">불러오는 중…</p>
              )}
            </div>
          </div>
        </div>

        <div className="rightCol">
          <div className="card">
            <div className="cardHeader">
              <div>
                <div className="h3">뉴스</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                  최근 {news.length}건 · tone은 GDELT 또는 RSS 추정치
                </div>
              </div>
            </div>
            <div className="cardBody">
              {news.length === 0 ? (
                <p className="muted">뉴스 데이터가 없습니다(ENABLE_NEWS 켜고 배치 재계산)</p>
              ) : (
                <div style={{ display: 'grid', gap: 10 }}>
                  {news.map((n, idx) => {
                    const t = n.tone == null ? null : Number(n.tone)
                    const cls = t == null ? 'pill scorePillNeu' : t > 0.5 ? 'pill scorePillPos' : t < -0.5 ? 'pill scorePillNeg' : 'pill scorePillNeu'
                    return (
                      <a
                        key={idx}
                        href={n.url}
                        target="_blank"
                        rel="noreferrer"
                        className="card"
                        style={{ padding: 12, boxShadow: 'none' }}
                      >
                        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', justifyContent: 'space-between' }}>
                          <div style={{ fontWeight: 800, lineHeight: 1.25 }}>{n.title}</div>
                          <span className={cls} title="tone">
                            {t == null || !Number.isFinite(t) ? '-' : t.toFixed(2)}
                          </span>
                        </div>
                        <div className="muted2" style={{ marginTop: 6, fontSize: 12 }}>
                          {n.source ?? 'source'} · {String(n.published_at ?? '').slice(0, 10)}
                        </div>
                      </a>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

