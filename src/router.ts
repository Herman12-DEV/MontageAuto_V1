// Routage par hash : « #/app/termine?id=abc » → chemin « /app/termine » + paramètres.
import { useEffect, useState } from 'react'

export type Route = { path: string; params: URLSearchParams }

export function currentRoute(): Route {
  const hash = window.location.hash
  if (!hash.startsWith('#/')) return { path: '/', params: new URLSearchParams() }
  const [rawPath, query = ''] = hash.slice(1).split('?')
  const path = rawPath.replace(/\/+$/, '')
  return { path: path === '' ? '/' : path, params: new URLSearchParams(query) }
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(currentRoute)
  useEffect(() => {
    const onHashChange = () => setRoute(currentRoute())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])
  return route
}

export function navigate(hash: string) {
  window.location.hash = hash
}
