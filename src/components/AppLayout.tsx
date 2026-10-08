import type { ReactNode } from 'react'
import { FolderOpen, LogOut, Plus, Settings2, UserRound } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

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

export default function AppLayout({ nav, children }: { nav: NavKey; children: ReactNode }) {
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
          <span className="app__status">
            <i className="dot dot--green" />
            Moteur IA en ligne
          </span>
          <a className="app__logout" href="#/connexion">
            <LogOut size={14} />
            Déconnexion
          </a>
        </div>
      </aside>
      <main className="app__main">{children}</main>
    </div>
  )
}
