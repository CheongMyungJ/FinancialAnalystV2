import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiDelete, apiGet, apiPost, apiPut } from '../../lib/api'

type Factor = {
  id: number
  key: string
  name: string
  description: string | null
  factor_type: string
  calculator: string
  weight: number
  higher_is_better: boolean
  normalize: string
  enabled: boolean
}

export function FactorsPage() {
  const nav = useNavigate()
  const [me, setMe] = useState<string | null>(null)
  const [items, setItems] = useState<Factor[]>([])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [presets, setPresets] = useState<Array<{ key: string; name: string; description: string | null }>>([])
  const [presetKey, setPresetKey] = useState<string>('tech_focus')

  const [newFactor, setNewFactor] = useState<Omit<Factor, 'id'>>({
    key: 'new_factor_key',
    name: '새 팩터',
    description: null,
    factor_type: 'technical',
    calculator: 'momentum_120d',
    weight: 0.0,
    higher_is_better: true,
    normalize: 'percentile',
    enabled: true,
  })

  async function load() {
    try {
      const meRes = await apiGet<{ username: string }>('/api/admin/auth/me')
      setMe(meRes.username)
    } catch {
      nav('/admin/login')
      return
    }

    const res = await apiGet<{ items: Factor[] }>('/api/admin/factors')
    setItems(res.items)
    const p = await apiGet<{ items: Array<{ key: string; name: string; description: string | null }> }>('/api/admin/presets')
    setPresets(p.items)
    if (p.items.length > 0 && !p.items.some((x) => x.key === presetKey)) {
      setPresetKey(p.items[0].key)
    }
  }

  useEffect(() => {
    load().catch((e) => setError(String(e?.message ?? e)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function onCreate() {
    setSaving(true)
    setError(null)
    try {
      await apiPost('/api/admin/factors', newFactor)
      await load()
    } catch (e: any) {
      setError(String(e?.message ?? e))
    } finally {
      setSaving(false)
    }
  }

  async function onSave(item: Factor) {
    setSaving(true)
    setError(null)
    try {
      const body = { ...item }
      delete (body as any).id
      await apiPut(`/api/admin/factors/${item.id}`, body)
      await load()
    } catch (e: any) {
      setError(String(e?.message ?? e))
    } finally {
      setSaving(false)
    }
  }

  async function onDelete(id: number) {
    if (!confirm('삭제할까요?')) return
    setSaving(true)
    setError(null)
    try {
      await apiDelete(`/api/admin/factors/${id}`)
      await load()
    } catch (e: any) {
      setError(String(e?.message ?? e))
    } finally {
      setSaving(false)
    }
  }

  async function onRecomputeAll() {
    setSaving(true)
    setError(null)
    try {
      await apiPost('/api/admin/jobs/recompute', { market: 'ALL' })
      alert('재계산을 시작했어요. 잠시 후 랭킹/상세를 새로고침 해주세요.')
    } catch (e: any) {
      setError(String(e?.message ?? e))
    } finally {
      setSaving(false)
    }
  }

  async function onApplyPreset() {
    if (!presetKey) return
    const p = presets.find((x) => x.key === presetKey)
    const ok = confirm(`프리셋을 적용할까요?\n\n- ${p?.name ?? presetKey}\n- 적용 후 기존 enabled/weight는 덮어씁니다.`)
    if (!ok) return
    setSaving(true)
    setError(null)
    try {
      await apiPost('/api/admin/presets/apply', { preset_key: presetKey })
      await load()
      alert('프리셋을 적용했어요. 이제 배치 재계산을 실행하세요.')
    } catch (e: any) {
      setError(String(e?.message ?? e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <div className="card">
        <div className="cardHeader">
          <div>
            <div className="h3">팩터/가중치 관리</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
              로그인 사용자: <b>{me ?? '-'}</b>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button onClick={onRecomputeAll} disabled={saving} className="btn btnPrimary" type="button">
              배치 재계산(ALL)
            </button>
            <Link to="/" className="btn btnGhost">
              ← 랭킹
            </Link>
          </div>
        </div>
        <div className="cardBody" style={{ display: 'grid', gap: 12 }}>
          {error ? <p className="error">{error}</p> : <p className="muted2">설정 변경 후 배치를 재계산하세요.</p>}

          <div className="card" style={{ padding: 12, boxShadow: 'none' }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontWeight: 850 }}>투자 성향 프리셋</div>
                <div className="muted2" style={{ fontSize: 12, marginTop: 2 }}>
                  기술중심 / 가치중심 / 모멘텀·이슈 중심 등
                </div>
              </div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                <select className="select" value={presetKey} onChange={(e) => setPresetKey(e.target.value)} style={{ width: 260 }}>
                  {presets.map((p) => (
                    <option key={p.key} value={p.key}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <button onClick={onApplyPreset} disabled={saving || !presetKey} className="btn" type="button">
                  프리셋 적용
                </button>
              </div>
            </div>
            {presets.find((x) => x.key === presetKey)?.description ? (
              <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                {presets.find((x) => x.key === presetKey)?.description}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="cardHeader">
          <div className="h3">새 팩터 추가</div>
          <div className="muted" style={{ fontSize: 12 }}>
            key는 고유해야 합니다.
          </div>
        </div>
        <div className="cardBody">
          <div className="fieldGrid">
            <label>
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                key
              </div>
              <input className="input" value={newFactor.key} onChange={(e) => setNewFactor({ ...newFactor, key: e.target.value })} />
            </label>
            <label>
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                name
              </div>
              <input className="input" value={newFactor.name} onChange={(e) => setNewFactor({ ...newFactor, name: e.target.value })} />
            </label>
            <label>
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                type
              </div>
              <select className="select" value={newFactor.factor_type} onChange={(e) => setNewFactor({ ...newFactor, factor_type: e.target.value })}>
                <option value="technical">technical</option>
                <option value="fundamental">fundamental</option>
                <option value="sentiment">sentiment</option>
              </select>
            </label>
            <label>
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                calculator
              </div>
              <input className="input" value={newFactor.calculator} onChange={(e) => setNewFactor({ ...newFactor, calculator: e.target.value })} />
            </label>
            <label>
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                weight
              </div>
              <input className="input" type="number" step="0.01" value={newFactor.weight} onChange={(e) => setNewFactor({ ...newFactor, weight: Number(e.target.value) })} />
            </label>
            <label>
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                enabled
              </div>
              <select className="select" value={newFactor.enabled ? 'Y' : 'N'} onChange={(e) => setNewFactor({ ...newFactor, enabled: e.target.value === 'Y' })}>
                <option value="Y">Y</option>
                <option value="N">N</option>
              </select>
            </label>
          </div>
          <div style={{ marginTop: 12 }}>
            <button onClick={onCreate} disabled={saving} className="btn" type="button">
              추가
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="cardHeader">
          <div className="h3">팩터 목록</div>
          <div className="muted" style={{ fontSize: 12 }}>
            저장 버튼으로 개별 반영
          </div>
        </div>
        <div className="cardBody">
          <table className="table">
            <thead>
              <tr>
                <th className="th">key</th>
                <th className="th">name</th>
                <th className="th">type</th>
                <th className="th">calculator</th>
                <th className="th" style={{ textAlign: 'right', width: 110 }}>
                  weight
                </th>
                <th className="th" style={{ textAlign: 'center', width: 90 }}>
                  enabled
                </th>
                <th className="th" style={{ textAlign: 'right', width: 160 }}>
                  actions
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.id} className="trHover">
                  <td className="td">{it.key}</td>
                  <td className="td">
                    <input
                      className="input"
                      value={it.name}
                      onChange={(e) => setItems((xs) => xs.map((x) => (x.id === it.id ? { ...x, name: e.target.value } : x)))}
                    />
                  </td>
                  <td className="td">
                    <select
                      className="select"
                      value={it.factor_type}
                      onChange={(e) => setItems((xs) => xs.map((x) => (x.id === it.id ? { ...x, factor_type: e.target.value } : x)))}
                    >
                      <option value="technical">technical</option>
                      <option value="fundamental">fundamental</option>
                      <option value="sentiment">sentiment</option>
                    </select>
                  </td>
                  <td className="td">
                    <input
                      className="input"
                      value={it.calculator}
                      onChange={(e) => setItems((xs) => xs.map((x) => (x.id === it.id ? { ...x, calculator: e.target.value } : x)))}
                    />
                  </td>
                  <td className="td" style={{ textAlign: 'right' }}>
                    <input
                      className="input"
                      style={{ width: 110, textAlign: 'right' }}
                      type="number"
                      step="0.01"
                      value={it.weight}
                      onChange={(e) => setItems((xs) => xs.map((x) => (x.id === it.id ? { ...x, weight: Number(e.target.value) } : x)))}
                    />
                  </td>
                  <td className="td" style={{ textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      checked={it.enabled}
                      onChange={(e) => setItems((xs) => xs.map((x) => (x.id === it.id ? { ...x, enabled: e.target.checked } : x)))}
                    />
                  </td>
                  <td className="td" style={{ textAlign: 'right' }}>
                    <button onClick={() => onSave(it)} disabled={saving} className="btn" type="button">
                      저장
                    </button>{' '}
                    <button onClick={() => onDelete(it.id)} disabled={saving} className="btn" type="button">
                      삭제
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

