export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(path, { credentials: 'include' })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error('GET ' + path + ' failed: ' + res.status + ' ' + text)
  }
  return (await res.json()) as T
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error('POST ' + path + ' failed: ' + res.status + ' ' + text)
  }
  return (await res.json()) as T
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error('PUT ' + path + ' failed: ' + res.status + ' ' + text)
  }
  return (await res.json()) as T
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(path, { method: 'DELETE', credentials: 'include' })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error('DELETE ' + path + ' failed: ' + res.status + ' ' + text)
  }
  return (await res.json()) as T
}
