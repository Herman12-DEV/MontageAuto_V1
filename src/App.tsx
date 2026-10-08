import { useEffect, useState } from 'react'
import type { ComponentType, ReactNode } from 'react'
import Landing from './components/Landing'
import Auth from './components/Auth'
import Projects from './components/Projects'
import NewProject from './components/NewProject'
import FinishedProject from './components/FinishedProject'
import Profile from './components/Profile'
import Settings from './components/Settings'
import AppLayout from './components/AppLayout'
import type { NavKey } from './components/AppLayout'
import { ToastHost } from './components/Toast'

type AppPage = {
  component: ComponentType
  nav: NavKey
}

const appPages: Record<string, AppPage> = {
  '/app': { component: Projects, nav: 'projets' },
  '/app/nouveau': { component: NewProject, nav: 'nouveau' },
  '/app/termine': { component: FinishedProject, nav: 'projets' },
  '/app/profil': { component: Profile, nav: 'profil' },
  '/app/reglages': { component: Settings, nav: 'reglages' },
}

function currentPath(): string {
  const hash = window.location.hash
  if (!hash.startsWith('#/')) return '/'
  const path = hash.slice(1).replace(/\/+$/, '')
  return path === '' ? '/' : path
}

export default function App() {
  const [path, setPath] = useState<string>(currentPath)

  useEffect(() => {
    const onHashChange = () => setPath(currentPath())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [path])

  let page: ReactNode = <Landing />
  if (path === '/inscription') {
    page = <Auth mode="inscription" />
  } else if (path === '/connexion') {
    page = <Auth mode="connexion" />
  } else if (appPages[path]) {
    const { component: Page, nav } = appPages[path]
    page = (
      <AppLayout nav={nav}>
        <Page />
      </AppLayout>
    )
  }

  return (
    <>
      <ToastHost />
      {page}
    </>
  )
}
