import { useEffect, useState } from 'react'
import { Pencil, Play, Plus, Trash2 } from 'lucide-react'
import { projectHref, statusLabel, statusTone } from '../data'
import { api, deleteProject, errorMessage, formatDay, formatDuration, formatSeconds, renameProject } from '../api'
import { showToast } from './Toast'
import type { Project } from '../api'

export default function Projects() {
  const [projects, setProjects] = useState<Project[] | null>(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<{ id: string; title: string } | null>(null)
  const [confirmId, setConfirmId] = useState<string | null>(null)

  const active = projects?.some((p) => p.status === 'queued' || p.status === 'processing') ?? false

  useEffect(() => {
    let alive = true
    const load = () =>
      api<{ projects: Project[] }>('/api/projects')
        .then((data) => {
          if (!alive) return
          setProjects(data.projects)
          setError('')
        })
        .catch((err) => alive && setError(errorMessage(err)))
    load()
    // Rafraîchissement automatique tant qu’un montage est en cours.
    const timer = active ? window.setInterval(load, 3000) : undefined
    return () => {
      alive = false
      if (timer) window.clearInterval(timer)
    }
  }, [active])

  const saveTitle = async () => {
    if (!editing || !editing.title.trim()) return
    try {
      const updated = await renameProject(editing.id, editing.title.trim())
      setProjects((list) => list?.map((p) => (p.id === updated.id ? { ...p, title: updated.title } : p)) ?? null)
      setEditing(null)
      showToast('Montage renommé.')
    } catch (err) {
      showToast(errorMessage(err))
    }
  }

  const remove = async (project: Project) => {
    if (confirmId !== project.id) {
      setConfirmId(project.id)
      return
    }
    try {
      await deleteProject(project)
      setProjects((list) => list?.filter((p) => p.id !== project.id) ?? null)
      setConfirmId(null)
      showToast('Montage supprimé, ainsi que sa vidéo source.')
    } catch (err) {
      showToast(errorMessage(err))
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="page-title">Vos montages</h1>
          <p className="page-sub">Créez, suivez et exportez vos vidéos. Elles restent disponibles 30 jours.</p>
        </div>
        <a className="btn btn--green" href="#/app/nouveau">
          <Plus size={14} />
          Nouveau montage
        </a>
      </header>
      {error && (
        <p className="upload-error" role="alert">
          {error}
        </p>
      )}
      {projects && projects.length === 0 && (
        <section className="card upload-card">
          <div className="card__head">
            <span className="tag">Projet / 00</span>
          </div>
          <h3 className="card__title">Aucun montage pour l’instant</h3>
          <p className="page-sub">Déposez votre première vidéo : silences coupés, sous-titres et format vertical en quelques minutes.</p>
          <p>
            <a className="btn btn--green btn--sm" href="#/app/nouveau">
              <Plus size={13} />
              Créer mon premier montage
            </a>
          </p>
        </section>
      )}
      <div className="project-grid">
        {projects?.map((project, i) => {
          const label = statusLabel[project.status]
          const tone = statusTone[label]
          const pct = Math.round(project.progress * 100)
          return (
            <div className="project-card" key={project.id}>
              <a className="project-card__link" href={projectHref(project)}>
                <div className="project-card__thumb">
                  <span className="tag">Projet / {String(projects.length - i).padStart(2, '0')}</span>
                  <span className="project-card__play">
                    <Play size={15} fill="currentColor" />
                  </span>
                </div>
                <div className="project-card__body">
                  {editing?.id === project.id ? (
                    <input
                      className="project-card__title-input"
                      value={editing.title}
                      maxLength={200}
                      autoFocus
                      aria-label="Nouveau titre du montage"
                      onClick={(event) => event.preventDefault()}
                      onChange={(event) => setEditing({ id: project.id, title: event.target.value })}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          event.preventDefault()
                          saveTitle()
                        }
                        if (event.key === 'Escape') setEditing(null)
                      }}
                    />
                  ) : (
                    <h3>{project.title}</h3>
                  )}
                  <span className="tag">
                    {formatDay(project.created_at)} •{' '}
                    {project.options?.mode === 'shorts'
                      ? `${project.options.shorts_count} shorts · ${formatSeconds(project.options.shorts_duration)}`
                      : formatDuration(project.duration_out ?? project.duration_in)}
                  </span>
                  <span className={`project-card__status status--${tone}`}>
                    <i className={`dot dot--${tone}`} />
                    {label}
                    {project.status === 'processing' ? ` · ${pct}%` : ''}
                  </span>
                </div>
              </a>
              <div className="project-card__actions">
                {editing?.id === project.id ? (
                  <>
                    <button type="button" className="link" onClick={saveTitle}>
                      Enregistrer
                    </button>
                    <button type="button" className="link" onClick={() => setEditing(null)}>
                      Annuler
                    </button>
                  </>
                ) : confirmId === project.id ? (
                  <>
                    <button type="button" className="link project-card__danger" onClick={() => remove(project)}>
                      Confirmer la suppression
                    </button>
                    <button type="button" className="link" onClick={() => setConfirmId(null)}>
                      Annuler
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      className="link"
                      onClick={() => {
                        setConfirmId(null)
                        setEditing({ id: project.id, title: project.title })
                      }}
                    >
                      <Pencil size={11} /> Renommer
                    </button>
                    <button type="button" className="link" onClick={() => remove(project)}>
                      <Trash2 size={11} /> Supprimer
                    </button>
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </>
  )
}
