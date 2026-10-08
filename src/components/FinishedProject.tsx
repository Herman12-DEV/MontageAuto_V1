import { useState } from 'react'
import { Download, Pause, Play } from 'lucide-react'
import { showToast } from './Toast'

export default function FinishedProject() {
  const [playing, setPlaying] = useState(false)
  const download = () => showToast('Téléchargement simulé — démo 100 % front.')

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="page-title">Montage terminé.</h1>
          <p className="page-sub">
            Votre vidéo est prête à être publiée. Consultez l’aperçu final, choisissez votre qualité
            d’export et téléchargez votre fichier MP4.
          </p>
        </div>
        <span className="pill pill--green">
          <i className="dot dot--green" />
          Succès
        </span>
      </header>
      <div className="result-grid">
        <section className="card player">
          <div className="card__head">
            <span className="tag">Aperçu vidéo</span>
            <span className="tag">1080p · 30 FPS</span>
          </div>
          <div className={`player__screen${playing ? ' player__screen--playing' : ''}`}>
            <button
              className="player__btn"
              onClick={() => setPlaying((value) => !value)}
              aria-label={playing ? 'Mettre la lecture en pause' : 'Lancer la lecture'}
            >
              {playing ? <Pause size={22} fill="currentColor" /> : <Play size={24} fill="currentColor" />}
            </button>
            <i className="player__progress" />
          </div>
          <p className="tag player__note">Prévisualisation finale prête à être téléchargée</p>
        </section>
        <section className="card export">
          <span className="tag">Export</span>
          <p className="export__lead">Votre vidéo est prête à être publiée.</p>
          <button className="btn btn--green btn--block" onClick={download}>
            <Download size={15} />
            Télécharger la vidéo
          </button>
          <div className="export__formats">
            <button className="format" onClick={download}>
              <span>MP4 · 1080p · 30 FPS</span>
              <Download size={14} />
            </button>
            <button className="format" onClick={download}>
              <span>MP4 · 4K · 30 FPS</span>
              <Download size={14} />
            </button>
          </div>
          <div className="export__note">
            <span className="tag">Formats disponibles</span>
            <p>
              Les exports sont livrés en format MP4, prêts à être publiés sur les réseaux sociaux,
              votre site ou vos campagnes.
            </p>
          </div>
        </section>
      </div>
    </>
  )
}
