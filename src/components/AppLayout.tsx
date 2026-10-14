import type { MouseEvent, ReactNode } from 'react'
import { FolderOpen, LogOut, Plus, Settings2, UserRound } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { clearSession, useEngineOnline, useUser } from '../api'
import type { Quota } from '../api'

export type NavKey = 'projets' | 'nouveau' | 'reglages' | 'profil'

type NavItem = {
  key: NavKey
  label: string
  href: string
  icon: LucideIcon
}

const navItems: NavItem[] = [
  { key: 'projets', label: 'Mes projets', href: '#/app', icon: FolderOpen },
  { key: 'nouveau', label: 'Nouveau montage', href: '#/app/nouveau', icon: Plus },
  { key: 'reglages', label: 'Réglages', href: '#/app/reglages', icon: Settings2 },
  { key: 'profil', label: 'Mon profil', href: '#/app/profil', icon: UserRound },
]

export function creditsLabel(quota: Quota): string {
  if (quota.unlimited) return `${quota.plan_label} · montages illimités`
  return `${quota.remaining}/${quota.limit} montages restants ce mois`
}

export default function AppLayout({ nav, children }: { nav: NavKey; children: ReactNode }) {
  const user = useUser()
  const online = useEngineOnline()

  const logout = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault()
    clearSession()
      .catch(() => undefined)
      .finally(() => {
        window.location.hash = '#/connexion'
      })
  }

  return (
    <div className="app">
      <aside className="app__sidebar">
        <a className="brand" href="#/">
          AutoCut
        </a>
        <p className="tag app__menu-label">Menu principal</p>
        <nav className="app__nav">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <a key={item.key} href={item.href} className={item.key === nav ? 'active' : undefined}>
                <Icon size={15} />
                {item.label}
              </a>
            )
          })}
        </nav>
        <div className="app__sidebar-foot">
          {user && (
            <a className="app__status" href="#/app/profil" title="Voir mon offre">
              <i className={`dot dot--${user.quota.unlimited || (user.quota.remaining ?? 0) > 0 ? 'green' : 'red'}`} />
              {creditsLabel(user.quota)}
            </a>
          )}
          <span className="app__status">
            <i className={`dot dot--${online === false ? 'red' : 'green'}`} />
            {online === false ? 'Moteur IA indisponible' : 'Moteur IA en ligne'}
          </span>
          <a className="app__logout" href="#/connexion" onClick={logout}>
            <LogOut size={14} />
            Déconnexion
          </a>
        </div>
      </aside>
      <main className="app__main">{children}</main>
    </div>
  )
}
