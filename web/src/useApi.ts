import { useCallback, useEffect, useState } from 'react'
import { getJson } from './api'

export interface ApiState<T> {
  data: T | undefined
  loading: boolean
  error: string | undefined
  reload: () => void
}

interface Loaded<T> { key: string | null; data: T | undefined; error: string | undefined }

/** Fetch JSON for `path`. Keeps the previous data while a new path loads (so charts hold their
 *  frame instead of flashing). `loading` is derived, not stored, so no setState runs in render or
 *  synchronously in the effect. `reload()` refetches the same path (the Retry button). */
export function useApi<T>(path: string | null): ApiState<T> {
  const [attempt, setAttempt] = useState(0)
  const [loaded, setLoaded] = useState<Loaded<T>>({ key: null, data: undefined, error: undefined })
  const key = path ? `${path}#${attempt}` : null

  useEffect(() => {
    if (!path || !key) return
    const ctrl = new AbortController()
    getJson<T>(path, ctrl.signal)
      .then((data) => setLoaded({ key, data, error: undefined }))
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return
        const error = e instanceof Error ? e.message : String(e)
        setLoaded((prev) => ({ key, data: prev.data, error }))
      })
    return () => ctrl.abort()
  }, [path, key])

  const reload = useCallback(() => setAttempt((a) => a + 1), [])
  return {
    data: loaded.data,
    loading: !!key && loaded.key !== key,
    error: loaded.key === key ? loaded.error : undefined,
    reload,
  }
}
