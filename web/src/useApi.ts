import { useEffect, useState } from 'react'
import { getJson } from './api'

export interface ApiState<T> { data: T | undefined; loading: boolean; error: string | undefined }

interface Loaded<T> { path: string | null; data: T | undefined; error: string | undefined }

/** Fetch JSON for `path`. Keeps the previous data while a new path loads (so charts hold their
 *  frame instead of flashing); `loading` is derived, not stored, so no setState runs in render
 *  or synchronously in the effect. */
export function useApi<T>(path: string | null): ApiState<T> {
  const [loaded, setLoaded] = useState<Loaded<T>>({ path: null, data: undefined, error: undefined })

  useEffect(() => {
    if (!path) return
    const ctrl = new AbortController()
    getJson<T>(path, ctrl.signal)
      .then((data) => setLoaded({ path, data, error: undefined }))
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return
        const error = e instanceof Error ? e.message : String(e)
        setLoaded((prev) => ({ path, data: prev.data, error }))
      })
    return () => ctrl.abort()
  }, [path])

  return {
    data: loaded.data,
    loading: !!path && loaded.path !== path,
    error: loaded.path === path ? loaded.error : undefined,
  }
}
