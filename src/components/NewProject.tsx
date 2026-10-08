import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, DragEvent, KeyboardEvent } from 'react'
import { ArrowRight, Check, FileVideo, Play, Upload } from 'lucide-react'

export default function NewProject() {
  const [progress, setProgress] = useState(0)
  const [running, setRunning] = useState(false)
  const [fileName, setFileName] = useState<string | null>(null)
  const [fileError, setFileError] = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const startAnalysis = () => {
    setProgress(0)
    setRunning(true)
  }

  useEffect(() => {
    // Démonstration : l’analyse se lance automatiquement à l’arrivée sur l’écran.
    startAnalysis()
  }, [])

  useEffect(() => {
    if (!running) return
    const timer = window.setInterval(() => {
      setProgress((current) => Math.min(62, current + 1.4 + Math.random() * 2.6))
    }, 110)
    return () => window.clearInterval(timer)
  }, [running])

  useEffect(() => {
    if (running && progress >= 62) setRunning(false)
  }, [running, progress])

  const handleFile = (file?: File) => {
    if (!file) return
    const extension = file.name.split('.').pop()?.toLowerCase()
    const supportedType = ['mp4', 'mov'].includes(extension ?? '')
    const supportedMime = file.type === '' || file.type.startsWith('video/')
    if (!supportedType || !supportedMime) {
      setFileError('Format non pris en charge. Choisissez une vidéo MP4 ou MOV.')
      return
    }
    if (file.size > 2 * 1024 * 1024 * 1024) {
      setFileError('La vidéo dépasse la limite de 2 Go.')
      return
    }
    setFileError('')
    setFileName(file.name)
    startAnalysis()
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

  const pct = Math.round(progress)
  const scenesDone = progress > 12
  const cutsDone = progress > 38
  const finished = progress >= 62

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="page-title">Nouveau montage</h1>
          <p className="page-sub">Importez votre vidéo. L’IA s’occupe du reste.</p>
        </div>
        <span className="pill pill--green">
          <i className="dot dot--green" />
          Moteur IA en ligne
        </span>
      </header>
      <div className="upload-grid">
        <section className="card upload-card">
          <div className="card__head">
            <span className="tag">Étape 01 | Import</span>
            <span className="tag">2 Go max</span>
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
              accept="video/mp4,video/quicktime,.mp4,.mov"
              hidden
              onChange={onInputChange}
            />
            <span className="dropzone__icon">
              <Upload size={18} />
            </span>
            <strong>Déposez votre vidéo ici</strong>
            <p>Glissez-déposez votre fichier ou choisissez un fichier depuis votre ordinateur.</p>
            <span className="btn btn--green btn--sm">Choisir un fichier</span>
            <span className="tag">MP4, MOV · 2 Go max</span>
          </div>
          {fileError && (
            <p className="upload-error" role="alert">
              {fileError}
            </p>
          )}
          {fileName && !fileError && (
            <span className="tag file-chip">
              <FileVideo size={12} />
              {fileName}
            </span>
          )}
        </section>
        <section className="card upload-card">
          <div className="card__head">
            <span className="tag">Étape 02 | Traitement</span>
            <span className="tag upload-card__pct">{pct}% terminé</span>
          </div>
          <h3 className="card__title">Analyse de la vidéo</h3>
          <div className="analysis">
            <div>
              <div className="analysis__row">
                <span className="tag">Progression de l’analyse</span>
                <span className="tag">{pct}%</span>
              </div>
              <div className="progress">
                <i style={{ width: `${pct}%` }} />
              </div>
            </div>
            <div className="chips">
              <div className={`chip${scenesDone ? ' chip--done' : ''}`}>
                <span className="tag">Scènes</span>
                <span>
                  {scenesDone ? (
                    <>
                      <Check size={11} />
                      Détection terminée
                    </>
                  ) : (
                    'En attente'
                  )}
                </span>
              </div>
              <div className={`chip${cutsDone ? ' chip--done' : ''}`}>
                <span className="tag">Coupes</span>
                <span>
                  {cutsDone ? (
                    <>
                      <Check size={11} />
                      14 coupes
                    </>
                  ) : (
                    'À venir'
                  )}
                </span>
              </div>
              <div className="chip">
                <span className="tag">Sous-titres</span>
                <span>À venir</span>
              </div>
              <div className="chip">
                <span className="tag">Recadrage</span>
                <span>À venir</span>
              </div>
            </div>
            <div className="analysis__preview">
              <div className="card__head">
                <span className="tag">Aperçu du montage</span>
                <span className="tag">{pct}% traité</span>
              </div>
              <div className="preview-box">
                <span className="preview-box__play">
                  <Play size={15} fill="currentColor" />
                </span>
              </div>
              <p className="tag preview-note">Votre aperçu apparaîtra ici automatiquement.</p>
            </div>
            {finished ? (
              <div className="analysis__done">
                <a className="btn btn--green" href="#/app/termine">
                  Voir le montage terminé
                  <ArrowRight size={14} />
                </a>
                <button type="button" className="link" onClick={startAnalysis}>
                  Relancer l’analyse
                </button>
              </div>
            ) : (
              <p className="tag analysis__hint">Analyse en cours…</p>
            )}
          </div>
        </section>
      </div>
    </>
  )
}
