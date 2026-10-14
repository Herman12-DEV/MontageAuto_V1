import type { Project, ProjectStatus as ApiStatus, Stage } from './api'

export type ProjectStatus = 'TERMINE' | 'EN COURS' | 'EN FILE' | 'ERREUR'

export const statusLabel: Record<ApiStatus, ProjectStatus> = {
  done: 'TERMINE',
  processing: 'EN COURS',
  queued: 'EN FILE',
  failed: 'ERREUR',
}

export const statusTone: Record<ProjectStatus, 'green' | 'yellow' | 'red'> = {
  TERMINE: 'green',
  'EN COURS': 'yellow',
  'EN FILE': 'yellow',
  ERREUR: 'red',
}

/** Étapes affichées pendant le traitement (F-TRT-04). */
export const stages: { key: Stage; label: string; done: string }[] = [
  { key: 'analyse', label: 'Analyse', done: 'Silences détectés' },
  { key: 'transcription', label: 'Transcription', done: 'Texte généré' },
  { key: 'montage', label: 'Montage', done: 'Sous-titres prêts' },
  { key: 'encodage', label: 'Encodage', done: 'Vidéo prête' },
]

const order: Stage[] = ['attente', 'analyse', 'transcription', 'montage', 'encodage', 'termine']

export function stageState(project: Project | null, stage: Stage): 'done' | 'active' | 'todo' {
  if (!project) return 'todo'
  if (project.status === 'done') return 'done'
  const current = order.indexOf(project.stage)
  const target = order.indexOf(stage)
  if (current > target) return 'done'
  if (current === target && project.status === 'processing') return 'active'
  return 'todo'
}

export function projectHref(project: Project): string {
  return project.status === 'done' || project.status === 'failed'
    ? `#/app/termine?id=${project.id}`
    : `#/app/nouveau?id=${project.id}`
}
