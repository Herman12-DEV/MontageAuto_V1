import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, DragEvent, FormEvent, KeyboardEvent } from 'react'
import { ArrowRight, Check, FileVideo, Play, Upload } from 'lucide-react'
import {
  ApiError,
  api,
  errorMessage,
  formatDuration,
  formatSeconds,
  getLibrary,
  refreshUser,
  uploadFile,
  deleteStoredFile,
  useEngineOnline,
  useUser,
} from '../api'
import type { Library, Project, ProjectOptions, StoredVideo } from '../api'
import { stageState, stages } from '../data'
import { showToast } from './Toast'

const EXTENSIONS = ['mp4', 'mov', 'webm', 'mkv', 'm4v']
const MAX_BYTES = 500 * 1024 * 1024

type Choices = Pick<
  ProjectOptions,
  | 'subtitle_style' | 'format' | 'language' | 'music' | 'silence_db' | 'padding_ms' | 'subtitles'
  | 'mode' | 'shorts_count' | 'shorts_duration'
>

export default function NewProject({ params }: { params: URLSearchParams }) {
  const user = useUser()
  const online = useEngineOnline()
  const [library, setLibrary] = useState<Library | null>(null)
  const [choices, setChoices] = useState<Choices | null>(null)

  const [fileName, setFileName] = useState<string | null>(null)
  const [fileError, setFileError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [uploadPct, setUploadPct] = useState<number | null>(null)
  // Vidéo envoyée dans Firebase Storage, prête à être montée.
  const [stored, setStored] = useState<StoredVideo | null>(null)
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [launchWhenReady, setLaunchWhenReady] = useState(false)
  const [starting, setStarting] = useState(false)

  const [project, setProject] = useState<Project | null>(null)
  const [pollKey, setPollKey] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const projectId = params.get('id')

  useEffect(() => {
    getLibrary().then(setLibrary).catch(() => undefined)
    return () => abortRef.current?.abort()
  }, [])

  // Préférences mémorisées du profil comme valeurs par défaut (F-CPT-05).
  useEffect(() => {
    if (!user || choices) return
    setChoices({
      subtitle_style: user.prefs.subtitle_style,
      format: user.prefs.format,
      language: user.prefs.language,
      music: null,
      silence_db: -35,
      padding_ms: 100,
      subtitles: true,
      mode: 'full',
      shorts_count: 3,
      shorts_duration: 30,
    })
  }, [user, choices])

  // Suivi d’un montage existant (?id=…) : interrogation régulière tant qu’il n’est pas fini.
  useEffect(() => {
    if (!projectId) {
      setProject(null)
      return
    }
    let alive = true
    let timer: number | undefined
    const load = async () => {
      try {
        const data = await api<Project>(`/api/projects/${projectId}`)
        if (!alive) return
        setProject(data)
        if (data.status === 'queued' || data.status === 'processing') {
          timer = window.setTimeout(load, 1500)
        } else {
          refreshUser().catch(() => undefined)
        }
      } catch (err) {
        if (!alive) return
        if (err instanceof ApiError && err.status === 404) {
          setFileError(errorMessage(err))
          return
        }
        // Serveur momentanément indisponible : on continue le suivi, sans figer la page.
        timer = window.setTimeout(load, 5000)
      }
    }
    load()
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [projectId, pollKey])

  const createProject = async (source: { storage?: StoredVideo; youtube_url?: string }) => {
    if (!choices) return
    setStarting(true)
    setFileError('')
    try {
      const created = await api<Project>('/api/projects', { body: { ...source, options: choices } })
      setProject(created)
      setStored(null)
      setLaunchWhenReady(false)
      refreshUser().catch(() => undefined)
      window.location.hash = `#/app/nouveau?id=${created.id}`
    } catch (err) {
      setLaunchWhenReady(false)
      setFileError(errorMessage(err))
      if (err instanceof ApiError && err.code === 'quota_exceeded') {
        showToast('Quota atteint — passez au plan Pro depuis votre profil.')
      }
    } finally {
      setStarting(false)
    }
  }

  // Lancement différé : l’utilisateur a cliqué avant la fin du téléversement.
  useEffect(() => {
    if (stored && launchWhenReady && !starting) createProject({ storage: stored })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stored, launchWhenReady])

  const handleFile = async (file?: File) => {
    if (!file) return
    const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
    const supportedMime = file.type === '' || file.type.startsWith('video/')
    if (!EXTENSIONS.includes(extension) || !supportedMime) {
      setFileError('Format non pris en charge. Choisissez une vidéo MP4, MOV, WebM ou MKV.')
      return
    }
    if (file.size > MAX_BYTES) {
      setFileError('La vidéo dépasse la limite de 500 Mo.')
      return
    }
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setFileError('')
    setFileName(file.name)
    // La vidéo précédente, envoyée mais non utilisée, est retirée du Storage.
    if (stored) deleteStoredFile(stored.path).catch(() => undefined)
    setStored(null)
    setUploadPct(0)
    if (projectId) window.location.hash = '#/app/nouveau'
    try {
      const done = await uploadFile(file, setUploadPct, controller.signal)
      setUploadPct(1)
      setStored(done)
      if (user?.prefs.auto_analyse) setLaunchWhenReady(true)
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      setUploadPct(null)
      setFileError(errorMessage(err))
    }
  }

  const launch = (event?: FormEvent) => {
    event?.preventDefault()
    if (youtubeUrl.trim()) {
      createProject({ youtube_url: youtubeUrl.trim() })
    } else if (stored) {
      createProject({ storage: stored })
    } else if (uploadPct !== null) {
      setLaunchWhenReady(true)
    } else {
      setFileError('Déposez d’abord une vidéo ou collez un lien YouTube.')
    }
  }

  const retry = async () => {
    if (!project) return
    try {
      setProject(await api<Project>(`/api/projects/${project.id}/retry`, { method: 'POST' }))
      setFileError('')
      setPollKey((key) => key + 1)
      refreshUser().catch(() => undefined)
    } catch (err) {
      setFileError(errorMessage(err))
    }
  }

  const reset = () => {
    abortRef.current?.abort()
    if (stored) deleteStoredFile(stored.path).catch(() => undefined)
    setFileName(null)
    setUploadPct(null)
    setStored(null)
    setYoutubeUrl('')
    setFileError('')
    window.location.hash = '#/app/nouveau'
  }

  const onInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    handleFile(event.target.files?.[0])
    event.target.value = ''
  }

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    handleFile(event.dataTransfer.files?.[0])
  }

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      inputRef.current?.click()
    }
  }

  const set = <K extends keyof Choices>(key: K, value: Choices[K]) =>
    setChoices((current) => (current ? { ...current, [key]: value } : current))

  const pct = project ? Math.round(project.progress * 100) : 0
  const tracking = project && (project.status === 'queued' || project.status === 'processing')
  const quota = user?.quota
  const outOfCredits = quota ? !quota.unlimited && (quota.remaining ?? 0) <= 0 : false
  const busy = starting || launchWhenReady

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="page-title">Nouveau montage</h1>
          <p className="page-sub">
            Importez votre vidéo. L’IA s’occupe du reste : silences coupés, sous-titres mot par mot,
            musique et recadrage — traitement 100 % automatisé.
          </p>
        </div>
        <span className={online === false ? 'pill' : 'pill pill--green'}>
          <i className={`dot dot--${online === false ? 'red' : 'green'}`} />
          {online === false ? 'Moteur IA indisponible' : 'Moteur IA en ligne'}
        </span>
      </header>
      <div className="upload-grid">
        <section className="card upload-card">
          <div className="card__head">
            <span className="tag">Étape 01 | Import</span>
            <span className="tag">500 Mo max</span>
          </div>
          <h3 className="card__title">Déposez votre vidéo</h3>
          <div
            className={`dropzone${dragging ? ' dropzone--drag' : ''}`}
            role="button"
            tabIndex={0}
            onClick={() => inputRef.current?.click()}
            onKeyDown={onKeyDown}
            onDragOver={(event) => {
              event.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <input
              ref={inputRef}
              type="file"
              accept="video/mp4,video/quicktime,video/webm,video/x-matroska,.mp4,.mov,.webm,.mkv,.m4v"
              hidden
              onChange={onInputChange}
            />
            <span className="dropzone__icon">
              <Upload size={18} />
            </span>
            <strong>Déposez votre vidéo ici</strong>
            <p>Glissez-déposez votre fichier ou choisissez un fichier depuis votre ordinateur.</p>
            <span className="btn btn--green btn--sm">Choisir un fichier</span>
            <span className="tag">MP4, MOV, WebM, MKV · 500 Mo max</span>
          </div>
          {fileError && (
            <p className="upload-error" role="alert">
              {fileError}{' '}
              {outOfCredits && (
                <a className="link" href="#/app/profil">
                  Passer au plan Pro
                </a>
              )}
            </p>
          )}
          {fileName && !fileError && (
            <span className="tag file-chip">
              <FileVideo size={12} />
              {fileName}
              {uploadPct !== null && uploadPct < 1 ? ` · envoi ${Math.round(uploadPct * 100)}%` : ''}
              {stored ? ' · prête' : ''}
            </span>
          )}
          {uploadPct !== null && uploadPct < 1 && (
            <div className="progress upload-progress">
              <i style={{ width: `${Math.round(uploadPct * 100)}%` }} />
            </div>
          )}

          <form className="options" onSubmit={launch}>
            <label className="field options__wide">
              <span className="tag">Ou collez un lien YouTube</span>
              <input
                type="url"
                placeholder="https://youtube.com/watch?v=…"
                value={youtubeUrl}
                onChange={(event) => setYoutubeUrl(event.target.value)}
              />
            </label>
            {library && choices && (
              <>
                <label className="field options__wide">
                  <span className="tag">Type de montage</span>
                  <select
                    value={choices.mode}
                    onChange={(event) => set('mode', event.target.value as Choices['mode'])}
                  >
                    <option value="full">Montage complet — toute la vidéo, sans les silences</option>
                    <option value="shorts">Shorts — plusieurs extraits courts prêts à publier</option>
                  </select>
                </label>
                {choices.mode === 'shorts' && (
                  <>
                    <label className="field">
                      <span className="tag">Nombre de shorts</span>
                      <select
                        value={choices.shorts_count}
                        onChange={(event) => set('shorts_count', Number(event.target.value))}
                      >
                        {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                          <option key={n} value={n}>
                            {n} short{n > 1 ? 's' : ''}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span className="tag">Durée de chaque short · {formatSeconds(choices.shorts_duration)}</span>
                      <input
                        type="range"
                        min={30}
                        max={150}
                        step={5}
                        value={choices.shorts_duration}
                        onChange={(event) => set('shorts_duration', Number(event.target.value))}
                        aria-label="Durée de chaque short, de 30 secondes à 2 minutes 30"
                      />
                    </label>
                  </>
                )}
                <label className="field">
                  <span className="tag">Style de sous-titres</span>
                  <select
                    value={choices.subtitles ? choices.subtitle_style : 'aucun'}
                    onChange={(event) => {
                      const value = event.target.value
                      set('subtitles', value !== 'aucun')
                      if (value !== 'aucun') set('subtitle_style', value)
                    }}
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
                    value={choices.format}
                    onChange={(event) => set('format', event.target.value as Choices['format'])}
                  >
                    {library.formats.map((format) => (
                      <option key={format.key} value={format.key}>
                        {format.label} — {format.hint}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span className="tag">Langue</span>
                  <select
                    value={choices.language}
                    onChange={(event) => set('language', event.target.value as Choices['language'])}
                  >
                    {library.languages.map((language) => (
                      <option key={language.key} value={language.key}>
                        {language.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span className="tag">Musique de fond</span>
                  <select
                    value={choices.music ?? ''}
                    onChange={(event) => set('music', event.target.value || null)}
                  >
                    <option value="">Sans musique</option>
                    {library.music.map((track) => (
                      <option key={track.id} value={track.id}>
                        {track.title}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span className="tag">Seuil de silence · {choices.silence_db} dB</span>
                  <input
                    type="range"
                    min={-60}
                    max={-20}
                    step={1}
                    value={choices.silence_db}
                    onChange={(event) => set('silence_db', Number(event.target.value))}
                  />
                </label>
                <label className="field">
                  <span className="tag">Respiration · {choices.padding_ms} ms</span>
                  <input
                    type="range"
                    min={0}
                    max={500}
                    step={20}
                    value={choices.padding_ms}
                    onChange={(event) => set('padding_ms', Number(event.target.value))}
                  />
                </label>
              </>
            )}
            <button
              className="btn btn--green btn--block options__wide"
              type="submit"
              disabled={busy || Boolean(tracking)}
            >
              {busy ? 'Lancement…' : 'Lancer le montage'}
              <ArrowRight size={14} />
            </button>
          </form>
        </section>
        <section className="card upload-card">
          <div className="card__head">
            <span className="tag">Étape 02 | Traitement</span>
            <span className="tag upload-card__pct">{pct}% terminé</span>
          </div>
          <h3 className="card__title">{project ? project.title : 'Analyse de la vidéo'}</h3>
          <div className="analysis">
            <div>
              <div className="analysis__row">
                <span className="tag">
                  {project?.status === 'queued'
                    ? `En file d’attente${project.queue_position ? ` · position ${project.queue_position}` : ''}`
                    : 'Progression de l’analyse'}
                </span>
                <span className="tag">{pct}%</span>
              </div>
              <div className="progress">
                <i style={{ width: `${pct}%` }} />
              </div>
            </div>
            <div className="chips">
              {stages.map((stage) => {
                const state = stageState(project, stage.key)
                return (
                  <div key={stage.key} className={`chip${state === 'done' ? ' chip--done' : ''}`}>
                    <span className="tag">{stage.label}</span>
                    <span>
                      {state === 'done' ? (
                        <>
                          <Check size={11} />
                          {stage.key === 'analyse' && project?.cuts != null
                            ? `${project.cuts} coupes`
                            : stage.done}
                        </>
                      ) : state === 'active' ? (
                        'En cours…'
                      ) : (
                        'À venir'
                      )}
                    </span>
                  </div>
                )
              })}
            </div>
            <div className="analysis__preview">
              <div className="card__head">
                <span className="tag">Aperçu du montage</span>
                <span className="tag">
                  {project?.status === 'done'
                    ? project.mode === 'shorts'
                      ? `${project.media?.shorts?.length ?? 0} shorts`
                      : `${formatDuration(project.duration_in)} → ${formatDuration(project.duration_out)}`
                    : `${pct}% traité`}
                </span>
              </div>
              <div className="preview-box">
                {project?.status === 'done' && (project.media?.video ?? project.media?.shorts?.[0]?.video) ? (
                  <video
                    className="preview-box__video"
                    src={project.media?.video ?? project.media?.shorts?.[0]?.video}
                    controls
                    playsInline
                    preload="metadata"
                  />
                ) : (
                  <span className="preview-box__play">
                    <Play size={15} fill="currentColor" />
                  </span>
                )}
              </div>
              <p className="tag preview-note">
                {project?.status === 'done'
                  ? project.mode === 'shorts'
                    ? `Aperçu du short 1 sur ${project.media?.shorts?.length ?? 0}`
                    : `${project.saved_pct ?? 0}% de temps gagné`
                  : 'Votre aperçu apparaîtra ici automatiquement.'}
              </p>
            </div>
            {project?.status === 'done' ? (
              <div className="analysis__done">
                <a className="btn btn--green" href={`#/app/termine?id=${project.id}`}>
                  {project.mode === 'shorts' ? 'Voir les shorts' : 'Voir le montage terminé'}
                  <ArrowRight size={14} />
                </a>
                <button type="button" className="link" onClick={reset}>
                  Nouveau montage
                </button>
              </div>
            ) : project?.status === 'failed' ? (
              <>
                <p className="upload-error" role="alert">
                  {project.error ?? 'Le montage a échoué.'} Votre crédit a été remboursé.
                </p>
                <div className="analysis__done">
                  <button type="button" className="btn btn--green" onClick={retry}>
                    Réessayer
                  </button>
                  <button type="button" className="link" onClick={reset}>
                    Importer une autre vidéo
                  </button>
                </div>
              </>
            ) : (
              <p className="tag analysis__hint">
                {tracking
                  ? 'Analyse en cours… Vous pouvez fermer cette page : nous vous prévenons par e-mail.'
                  : uploadPct !== null && uploadPct < 1
                    ? 'Envoi de la vidéo en cours…'
                    : 'En attente d’une vidéo.'}
              </p>
            )}
          </div>
        </section>
      </div>
    </>
  )
}
