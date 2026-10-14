import { useEffect } from 'react'
import type { ComponentType, ReactNode } from 'react'
import Landing from './components/Landing'
import Auth from './components/Auth'
import Projects from './components/Projects'
import NewProject from './components/NewProject'
import FinishedProject from './components/FinishedProject'
import Profile from './components/Profile'
import Settings from './components/Settings'
import InfoPage, { infoPages } from './components/InfoPage'
import AppLayout from './components/AppLayout'
import type { NavKey } from './components/AppLayout'
import { ToastHost } from './components/Toast'
import { useAuthState } from './api'
import { useRoute } from './router'

type AppPage = {
  component: ComponentType<{ params: URLSearchParams }>
  nav: NavKey
}

const appPages: Record<string, AppPage> = {
  '/app': { component: Projects, nav: 'projets' },
  '/app/nouveau': { component: NewProject, nav: 'nouveau' },
  '/app/termine': { component: FinishedProject, nav: 'projets' },
  '/app/profil': { component: Profile, nav: 'profil' },
  '/app/reglages': { component: Settings, nav: 'reglages' },
}

export default function App() {
  const { path, params } = useRoute()
  const protectedPage = Boolean(appPages[path])
  // Firebase restaure la session de façon asynchrone : on attend avant de rediriger.
  const { ready, loggedIn } = useAuthState()

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [path])

  useEffect(() => {
    // Espace connecté : sans session, on renvoie vers la connexion (puis on revient ici).
    if (!ready) return
    if (protectedPage && !loggedIn) {
      try {
        window.sessionStorage.setItem('autocut.next', window.location.hash)
      } catch {
        // stockage indisponible : on reviendra simplement sur le tableau de bord
      }
      window.location.hash = '#/connexion'
    }
    if ((path === '/connexion' || path === '/inscription') && loggedIn) {
      window.location.hash = '#/app'
    }
  }, [path, protectedPage, loggedIn, ready])

  let page: ReactNode = <Landing />
  if (path === '/inscription') {
    page = <Auth mode="inscription" />
  } else if (path === '/connexion') {
    page = <Auth mode="connexion" />
  } else if (path === '/confirmer' || path === '/reinitialiser') {
    // Anciens liens e-mail : la réinitialisation passe désormais par la page de Firebase.
    page = <Auth mode="connexion" />
  } else if (infoPages[path]) {
    page = <InfoPage path={path} />
  } else if (appPages[path] && !ready) {
    page = <p className="tag analysis__hint">Chargement de votre session…</p>
  } else if (appPages[path] && loggedIn) {
    const { component: Page, nav } = appPages[path]
    page = (
      <AppLayout nav={nav}>
        <Page params={params} />
      </AppLayout>
    )
  } else if (appPages[path]) {
    page = null
  }

  return (
    <>
      <ToastHost />
      {page}
    </>
  )
}
