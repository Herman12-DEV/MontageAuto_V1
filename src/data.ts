export type ProjectStatus = 'TERMINE' | 'EN COURS' | 'A TRAITER'

export type Project = {
  title: string
  date: string
  length: string
  status: ProjectStatus
  href: string
  index: string
}

export const projects: Project[] = [
  {
    title: 'Campagne été',
    date: 'Aujourd’hui',
    length: '01:24',
    status: 'TERMINE',
    href: '#/app/termine',
    index: '01',
  },
  {
    title: 'Reel produit',
    date: 'Aujourd’hui',
    length: '01:02',
    status: 'EN COURS',
    href: '#/app/nouveau',
    index: '02',
  },
  {
    title: 'Interview client',
    date: 'Aujourd’hui',
    length: '01:32',
    status: 'A TRAITER',
    href: '#/app/nouveau',
    index: '03',
  },
]

export const statusTone: Record<ProjectStatus, 'green' | 'yellow' | 'red'> = {
  TERMINE: 'green',
  'EN COURS': 'yellow',
  'A TRAITER': 'red',
}
