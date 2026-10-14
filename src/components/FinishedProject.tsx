import { useEffect, useRef, useState } from 'react'
import type { FormEvent, MouseEvent } from 'react'
import { ArrowRight, Download, Pause, Play } from 'lucide-react'
import { showToast } from './Toast'
import { ApiError, api, deleteProject, errorMessage, renameProject, formatDate, formatDuration, formatSeconds, getLibrary, refreshUser } from '../api'
import type { Library, Phrase, Project, ProjectOptions } from '../api'

type Restyle = Pick<
  ProjectOptions,
  'subtitle_style' | 'format' | 'music' | 'subtitles' | 'mode' | 'shorts_count' | 'shorts_duration'
>

export default function FinishedProject({ params }: { params: URLSearchParams }) {
  const id = params.get('id')
  const [project, setProject] = useState<Project | null>(null)
  const [error, setError] = useState('')
  const [pollKey, setPollKey] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [position, setPosition] = useState(0)
  const videoRef = useRef<HTMLVideoElement>(null)

  const [library, setLibrary] = useState<Library | null>(null)
  const [restyle, setRestyle] = useState<Restyle | null>(null)
  const [phrases, setPhrases] = useState<Phrase[] | null>(null)
  const [edited, setEdited] = useState<Record<number, string>>({})
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [title, setTitle] = useState('')
  const [shortIndex, setShortIndex] = useState(0)

  useEffect(() => {
    getLibrary().then(setLibrary).catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!id) {
      window.location.hash = '#/app'
      return
    }
    let alive = true
    let timer: number | undefined
    const load = async () => {
      try {
        const data = await api<Project>(`/api/projects/${id}`)
        if (!alive) return
        setProject(data)
        setRestyle({
          subtitle_style: data.options.subtitle_style,
          format: data.options.format,
          music: data.options.music,
          subtitles: data.options.subtitles,
          mode: data.options.mode ?? 'full',
          shorts_count: data.options.shorts_count ?? 3,
          shorts_duration: data.options.shorts_duration ?? 30,
        })
        if (data.status === 'queued' || data.status === 'processing') {
          timer = window.setTimeout(load, 1500)
        } else if (data.status === 'done' && data.has_transcript) {
          const transcript = await api<{ phrases: Phrase[] }>(`/api/projects/${id}/transcript`)
          if (alive) {
            setPhrases(transcript.phrases)
            setEdited({})
          }
        }
      } catch (err) {
        if (!alive) return
        if (err instanceof ApiError && err.status === 404) {
          setError(errorMessage(err))
          return
        }
        // Serveur momentanément indisponible : on continue le suivi sans figer la page.
        timer = window.setTimeout(load, 5000)
      }
    }
    load()
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [id, pollKey])

  const togglePlay = () => {
    const video = videoRef.current
    if (!video) return
    if (video.paused) video.play().catch(() => undefined)
    else video.pause()
  }

  const seek = (event: MouseEvent<HTMLElement>) => {
    const video = videoRef.current
    if (!video || !video.duration) return
    const rect = event.currentTarget.getBoundingClientRect()
    video.currentTime = ((event.clientX - rect.left) / rect.width) * video.duration
  }

  const retry = async () => {
    if (!project) return
    try {
      await api(`/api/projects/${project.id}/retry`, { method: 'POST' })
      refreshUser().catch(() => undefined)
      window.location.hash = `#/app/nouveau?id=${project.id}`
    } catch (err) {
      showToast(errorMessage(err))
    }
  }

  const applyRestyle = async () => {
    if (!project || !restyle) return
    setSaving(true)
    try {
      setProject(await api<Project>(`/api/projects/${project.id}/rerender`, { body: { options: restyle } }))
      setPollKey((key) => key + 1)
      showToast('Nouveau rendu lancé — sans crédit supplémentaire.')
    } catch (err) {
      showToast(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const saveTranscript = async () => {
    if (!project) return
    const changes = Object.entries(edited).map(([index, text]) => ({ index: Number(index), text }))
    if (!changes.length) {
      showToast('Aucune modification à enregistrer.')
      return
    }
    setSaving(true)
    try {
      setProject(await api<Project>(`/api/projects/${project.id}/transcript`, { method: 'PUT', body: { phrases: changes } }))
      setPollKey((key) => key + 1)
      showToast('Sous-titres corrigés — réincrustation en cours.')
    } catch (err) {
      showToast(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const removeProject = async () => {
    if (!project) return
    if (!confirmDelete) {
      setConfirmDelete(true)
      return
    }
    try {
      await deleteProject(project)
      showToast('Montage supprimé, ainsi que sa vidéo source.')
      window.location.hash = '#/app'
    } catch (err) {
      showToast(errorMessage(err))
    }
  }

  const saveTitle = async (event: FormEvent) => {
    event.preventDefault()
    if (!project || !title.trim()) return
    try {
      const updated = await renameProject(project.id, title.trim())
      setProject((current) => (current ? { ...current, title: updated.title } : current))
      setRenaming(false)
      showToast('Montage renommé.')
    } catch (err) {
      showToast(errorMessage(err))
    }
  }

  if (error) {
    return (
      <header className="page-head">
        <div>
          <h1 className="page-title">Montage introuvable.</h1>
          <p className="page-sub">{error}</p>
        </div>
        <a className="btn btn--green" href="#/app">
          Mes projets
        </a>
      </header>
    )
  }
  if (!project) return <p className="tag analysis__hint">Chargement…</p>

  const failed = project.status === 'failed'
  const rendering = project.status === 'queued' || project.status === 'processing'
  const media = project.media ?? {}
  const pct = Math.round(project.progress * 100)
  const isShorts = project.mode === 'shorts'
  const shortsList = media.shorts ?? []
  const currentShort = isShorts ? shortsList[Math.min(shortIndex, Math.max(0, shortsList.length - 1))] : undefined
  const videoSrc = isShorts ? currentShort?.video : media.video
  const downloadSrc = isShorts ? currentShort?.video_download : media.video_download
  const quality = project.height ? `${Math.min(project.width ?? 0, project.height)}p · ${Math.round(project.fps ?? 30)} FPS` : '—'

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="page-title">
            {failed ? 'Montage interrompu.' : rendering ? 'Rendu en cours.' : isShorts ? 'Shorts prêts.' : 'Montage terminé.'}
          </h1>
          <p className="page-sub">
            {failed
              ? `${project.error ?? 'Le traitement a échoué.'} Votre crédit a été automatiquement remboursé.`
              : rendering
                ? `Nouveau rendu de « ${project.title} » : ${pct}%. L’aperçu se mettra à jour automatiquement.`
                : isShorts
                  ? `${shortsList.length} short${shortsList.length > 1 ? 's' : ''} prêt${shortsList.length > 1 ? 's' : ''} à publier. Choisissez-en un pour l’aperçu, puis téléchargez-les.`
                  : 'Votre vidéo est prête à être publiée. Consultez l’aperçu final et téléchargez votre fichier MP4.'}
          </p>
        </div>
        <span className={failed || rendering ? 'pill' : 'pill pill--green'}>
          <i className={`dot dot--${failed ? 'red' : rendering ? 'yellow' : 'green'}`} />
          {failed ? 'Erreur' : rendering ? 'Traitement' : 'Succès'}
        </span>
      </header>
      {failed ? (
        <div className="analysis__done">
          <button type="button" className="btn btn--green" onClick={retry}>
            Réessayer
          </button>
          <a className="link" href="#/app/nouveau">
            Importer une autre vidéo
          </a>
        </div>
      ) : (
        <div className="result-grid">
          <section className="card player">
            <div className="card__head">
              <span className="tag">
                {isShorts && currentShort
                  ? `Short ${currentShort.index}/${shortsList.length} · ${formatSeconds(currentShort.duration)}`
                  : `Aperçu vidéo · ${project.title}`}
              </span>
              <span className="tag">{quality}</span>
            </div>
            <div className={`player__screen${playing ? ' player__screen--playing' : ''}`}>
              {videoSrc && !rendering && (
                <video
                  key={videoSrc}
                  ref={videoRef}
                  className="player__video"
                  src={videoSrc}
                  playsInline
                  preload="metadata"
                  onClick={togglePlay}
                  onPlay={() => setPlaying(true)}
                  onPause={() => setPlaying(false)}
                  onEnded={() => setPlaying(false)}
                  onTimeUpdate={(event) => {
                    const v = event.currentTarget
                    setPosition(v.duration ? v.currentTime / v.duration : 0)
                  }}
                />
              )}
              {!playing && (
                <button
                  className="player__btn"
                  onClick={togglePlay}
                  aria-label="Lancer la lecture"
                  disabled={rendering}
                >
                  <Play size={24} fill="currentColor" />
                </button>
              )}
              {playing && (
                <button className="player__btn player__btn--overlay" onClick={togglePlay} aria-label="Mettre la lecture en pause">
                  <Pause size={22} fill="currentColor" />
                </button>
              )}
              <i
                className="player__progress"
                onClick={seek}
                style={{
                  background: `linear-gradient(90deg, var(--green) ${(rendering ? pct / 100 : position) * 100}%, #343530 ${(rendering ? pct / 100 : position) * 100}%)`,
                }}
              />
            </div>
            <p className="tag player__note">
              {rendering
                ? `Rendu en cours · ${pct}%`
                : isShorts && currentShort
                  ? `« ${currentShort.title} » · disponible jusqu’au ${formatDate(project.expires_at)}`
                  : `Prévisualisation finale · disponible jusqu’au ${formatDate(project.expires_at)}`}
            </p>
          </section>
          <section className="card export">
            <span className="tag">Export</span>
            <p className="export__lead">
              {isShorts ? 'Vos shorts sont prêts à être publiés.' : 'Votre vidéo est prête à être publiée.'}
            </p>
            {downloadSrc && !rendering ? (
              <a className="btn btn--green btn--block" href={downloadSrc} download>
                <Download size={15} />
                {isShorts && currentShort ? `Télécharger le short ${currentShort.index}` : 'Télécharger la vidéo'}
              </a>
            ) : (
              <button className="btn btn--green btn--block" disabled>
                <Download size={15} />
                Rendu en cours…
              </button>
            )}
            <div className="export__formats">
              {isShorts &&
                !rendering &&
                shortsList.map((item, i) => (
                  <div className={`format${i === shortIndex ? ' format--active' : ''}`} key={item.index}>
                    <button
                      type="button"
                      className="format__pick"
                      onClick={() => {
                        setShortIndex(i)
                        setPlaying(false)
                        setPosition(0)
                      }}
                      title={item.title}
                    >
                      Short {item.index} · {formatSeconds(item.duration)} — {item.title}
                    </button>
                    {item.srt && (
                      <a href={item.srt} download className="format__srt" aria-label={`Sous-titres du short ${item.index}`}>
                        SRT
                      </a>
                    )}
                    <a href={item.video_download} download aria-label={`Télécharger le short ${item.index}`}>
                      <Download size={14} />
                    </a>
                  </div>
                ))}
              {media.video_download && (
                <a className="format" href={media.video_download} download>
                  <span>
                    MP4 · {project.width}×{project.height} · H.264
                  </span>
                  <Download size={14} />
                </a>
              )}
              {media.srt && (
                <a className="format" href={media.srt} download>
                  <span>Sous-titres · SRT</span>
                  <Download size={14} />
                </a>
              )}
              {media.ass && (
                <a className="format" href={media.ass} download>
                  <span>Sous-titres stylés · ASS</span>
                  <Download size={14} />
                </a>
              )}
              {media.txt && (
                <a className="format" href={media.txt} download>
                  <span>Transcription · TXT</span>
                  <Download size={14} />
                </a>
              )}
            </div>
            <div className="export__note">
              <span className="tag">{isShorts ? 'Extraits' : 'Avant / après'}</span>
              {isShorts ? (
                <p>
                  {shortsList.length} short{shortsList.length > 1 ? 's' : ''} de{' '}
                  {formatSeconds(project.options.shorts_duration)} maximum, tirés d’une vidéo de{' '}
                  {formatDuration(project.duration_in)} · {project.cuts ?? 0} silences coupés
                  {project.language ? ` · langue détectée : ${project.language.toUpperCase()}` : ''}.
                  {shortsList.length < project.options.shorts_count &&
                    ` La vidéo est trop courte pour ${project.options.shorts_count} shorts distincts.`}
                </p>
              ) : (
                <p>
                  Durée {formatDuration(project.duration_in)} → {formatDuration(project.duration_out)} ·{' '}
                  {project.saved_pct ?? 0}% de temps gagné · {project.cuts ?? 0} coupes
                  {project.language ? ` · langue détectée : ${project.language.toUpperCase()}` : ''}.
                </p>
              )}
            </div>
          </section>
        </div>
      )}

      {!failed && library && restyle && (
        <div className="result-grid result-grid--tools">
          <section className="card upload-card">
            <div className="card__head">
              <span className="tag">Sous-titres</span>
              <span className="tag">{phrases ? `${phrases.length} phrases` : '—'}</span>
            </div>
            <h3 className="card__title">Corriger le texte</h3>
            {phrases && phrases.length > 0 ? (
              <div className="transcript">
                {phrases.map((phrase) => (
                  <label className="field" key={phrase.index}>
                    <span className="tag">
                      {formatDuration(phrase.start)} → {formatDuration(phrase.end)}
                    </span>
                    <input
                      value={edited[phrase.index] ?? phrase.text}
                      onChange={(event) => setEdited((current) => ({ ...current, [phrase.index]: event.target.value }))}
                    />
                  </label>
                ))}
                <button className="btn btn--green btn--sm" onClick={saveTranscript} disabled={saving || rendering}>
                  Enregistrer et réincruster
                  <ArrowRight size={13} />
                </button>
              </div>
            ) : (
              <p className="page-sub">
                {rendering ? 'Disponible à la fin du rendu.' : 'Aucune parole détectée dans cette vidéo.'}
              </p>
            )}
          </section>
          <section className="card export">
            <span className="tag">Habillage</span>
            <p className="export__lead">Changez de style, de format ou de type de montage sans consommer de crédit.</p>
            <div className="options options--single">
              <label className="field">
                <span className="tag">Type de montage</span>
                <select
                  value={restyle.mode}
                  onChange={(event) => setRestyle({ ...restyle, mode: event.target.value as Restyle['mode'] })}
                >
                  <option value="full">Montage complet</option>
                  <option value="shorts">Shorts</option>
                </select>
              </label>
              {restyle.mode === 'shorts' && (
                <>
                  <label className="field">
                    <span className="tag">Nombre de shorts</span>
                    <select
                      value={restyle.shorts_count}
                      onChange={(event) => setRestyle({ ...restyle, shorts_count: Number(event.target.value) })}
                    >
                      {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                        <option key={n} value={n}>
                          {n} short{n > 1 ? 's' : ''}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span className="tag">Durée de chaque short · {formatSeconds(restyle.shorts_duration)}</span>
                    <input
                      type="range"
                      min={30}
                      max={150}
                      step={5}
                      value={restyle.shorts_duration}
                      onChange={(event) => setRestyle({ ...restyle, shorts_duration: Number(event.target.value) })}
                    />
                  </label>
                </>
              )}
              <label className="field">
                <span className="tag">Style de sous-titres</span>
                <select
                  value={restyle.subtitles ? restyle.subtitle_style : 'aucun'}
                  onChange={(event) =>
                    setRestyle({
                      ...restyle,
                      subtitles: event.target.value !== 'aucun',
                      subtitle_style: event.target.value === 'aucun' ? restyle.subtitle_style : event.target.value,
                    })
                  }
                >
                  {library.styles.map((style) => (
                    <option key={style.key} value={style.key}>
                      {style.label}
                    </option>
                  ))}
                  <option value="aucun">Sans sous-titres</option>
                </select>
              </label>
              <label className="field">
                <span className="tag">Format</span>
                <select
                  value={restyle.format}
                  onChange={(event) => setRestyle({ ...restyle, format: event.target.value as Restyle['format'] })}
                >
                  {library.formats.map((format) => (
                    <option key={format.key} value={format.key}>
                      {format.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="tag">Musique de fond</span>
                <select
                  value={restyle.music ?? ''}
                  onChange={(event) => setRestyle({ ...restyle, music: event.target.value || null })}
                >
                  <option value="">Sans musique</option>
                  {library.music.map((track) => (
                    <option key={track.id} value={track.id}>
                      {track.title}
                    </option>
                  ))}
                </select>
              </label>
              <button className="btn btn--ghost btn--block" onClick={applyRestyle} disabled={saving || rendering}>
                Appliquer
              </button>
            </div>
            <div className="export__note">
              <span className="tag">Gestion</span>
              {renaming ? (
                <form className="field rename-form" onSubmit={saveTitle}>
                  <input
                    value={title}
                    maxLength={200}
                    required
                    autoFocus
                    aria-label="Nouveau titre du montage"
                    onChange={(event) => setTitle(event.target.value)}
                  />
                  <p>
                    <button type="submit" className="link">
                      Enregistrer
                    </button>
                    {' · '}
                    <button type="button" className="link" onClick={() => setRenaming(false)}>
                      Annuler
                    </button>
                  </p>
                </form>
              ) : (
                <p>
                  <button
                    type="button"
                    className="link"
                    onClick={() => {
                      setTitle(project.title)
                      setRenaming(true)
                    }}
                  >
                    Renommer ce montage
                  </button>
                </p>
              )}
              <p>
                <button type="button" className="link" onClick={removeProject}>
                  {confirmDelete ? 'Confirmer la suppression définitive' : 'Supprimer ce montage'}
                </button>
                {confirmDelete && (
                  <>
                    {' · '}
                    <button type="button" className="link" onClick={() => setConfirmDelete(false)}>
                      Annuler
                    </button>
                  </>
                )}
              </p>
            </div>
          </section>
        </div>
      )}
    </>
  )
}
