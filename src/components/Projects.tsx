import { Play, Plus } from 'lucide-react'
import { projects, statusTone } from '../data'

export default function Projects() {
  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="page-title">Vos montages</h1>
          <p className="page-sub">Créez, suivez et exportez vos vidéos.</p>
        </div>
        <a className="btn btn--green" href="#/app/nouveau">
          <Plus size={14} />
          Nouveau montage
        </a>
      </header>
      <div className="project-grid">
        {projects.map((project) => {
          const tone = statusTone[project.status]
          return (
            <a className="project-card" key={project.title} href={project.href}>
              <div className="project-card__thumb">
                <span className="tag">Projet / {project.index}</span>
                <span className="project-card__play">
                  <Play size={15} fill="currentColor" />
                </span>
              </div>
              <div className="project-card__body">
                <h3>{project.title}</h3>
                <span className="tag">
                  {project.date} • {project.length}
                </span>
                <span className={`project-card__status status--${tone}`}>
                  <i className={`dot dot--${tone}`} />
                  {project.status}
                </span>
              </div>
            </a>
          )
        })}
      </div>
    </>
  )
}
