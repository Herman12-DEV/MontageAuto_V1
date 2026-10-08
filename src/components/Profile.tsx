import { ArrowRight, Pencil } from 'lucide-react'
import { showToast } from './Toast'

export default function Profile() {
  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="page-title">Mon profil.</h1>
          <p className="page-sub">Gérez vos informations et votre abonnement.</p>
        </div>
        <div className="page-head__actions">
          <a className="btn btn--ghost" href="#/app/nouveau">
            Nouveau montage
            <ArrowRight size={14} />
          </a>
          <button
            className="btn btn--white"
            onClick={() => showToast('Modification du profil — démo 100 % front.')}
          >
            <Pencil size={13} />
            Modifier le profil
          </button>
        </div>
      </header>
      <div className="profile-grid">
        <section className="card profile-card">
          <div className="card__head">
            <span className="tag">Informations personnelles</span>
            <span className="pill pill--green">Profil actif</span>
          </div>
          <dl className="profile-fields">
            <div>
              <dt className="tag">Nom</dt>
              <dd>Kouadio Herman</dd>
            </div>
            <div>
              <dt className="tag">Email</dt>
              <dd>vous@exemple.com</dd>
            </div>
          </dl>
          <button
            className="btn btn--ghost btn--sm"
            onClick={() => showToast('Modification du profil — démo 100 % front.')}
          >
            Modifier
          </button>
        </section>
        <section className="card profile-card">
          <div className="card__head">
            <span className="tag">Abonnement</span>
            <span className="pill pill--green">Actif</span>
          </div>
          <div>
            <p className="plan-name">Plan gratuit</p>
            <p className="plan-sub">Montages limités • Export jusqu’en 1080p</p>
          </div>
          <hr className="divider" />
          <div>
            <span className="tag">Prochain renouvellement</span>
            <p className="plan-name">Plan Pro</p>
          </div>
          <button
            className="btn btn--green btn--block"
            onClick={() => showToast('Passage au plan Pro — démo 100 % front.')}
          >
            Passer au plan Pro
          </button>
        </section>
      </div>
    </>
  )
}
