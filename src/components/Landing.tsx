import { ArrowRight, Play } from 'lucide-react'

export default function Landing() {
  return (
    <div className="landing">
      <header className="hero">
        <div className="container hero__top">
          <span className="tag">Montage vidéo automatique / 01</span>
          <nav className="hero__nav">
            <a href="#produit">Produit</a>
            <a href="#fonctionnement">Fonctionnement</a>
            <a href="#/app/profil">Tarifs</a>
            <a href="#/connexion">Connexion</a>
          </nav>
        </div>
        <div className="container hero__grid">
          <div>
            <h1 className="hero__title">
              Montez
              <br />
              moins.
              <br />
              Publiez plus.
            </h1>
            <p className="hero__sub">
              Transformez vos rushs en vidéos prêtes à publier. Coupez. Sous-titrez. Recadrez. Exportez.
            </p>
            <div className="hero__actions">
              <a className="btn btn--white" href="#/inscription">
                Commencer à créer
                <ArrowRight size={15} />
              </a>
              <a className="btn btn--green" href="#/app">
                <Play size={13} fill="currentColor" />
                Voir la démo
              </a>
            </div>
            <p className="tag hero__note">02:14 de rush → 00:32 prêt à publier. Sans timeline.</p>
          </div>
          <div className="hero__visual">
            <div className="window">
              <div className="window__bar">
                <span className="window__dots">
                  <i />
                  <i />
                  <i />
                </span>
                <span className="tag">AutoCut — Projet 01</span>
                <span className="tag">01:24</span>
              </div>
              <div className="window__video">
                <span className="window__play">
                  <Play size={18} fill="currentColor" />
                </span>
              </div>
              <div className="window__timeline">
                <i className="seg seg--green" style={{ flex: 34 }} />
                <i className="seg seg--yellow" style={{ flex: 12 }} />
                <i className="seg seg--green" style={{ flex: 28 }} />
                <i className="seg seg--red" style={{ flex: 10 }} />
              </div>
              <div className="window__times tag">
                <span>00:00</span>
                <span>00:32</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <section className="section" id="promesse">
        <div className="container">
          <div className="section__head">
            <span className="tag">01 | La promesse</span>
          </div>
          <div className="split">
            <h2 className="title">Votre vidéo,<br />sans la timeline.</h2>
            <p className="lead">
              AutoCut analyse vos rushs, comprend votre histoire et crée automatiquement un premier
              montage.
            </p>
          </div>
        </div>
      </section>

      <section className="section" id="produit">
        <div className="container">
          <h2 className="title">Des rush à la publication.</h2>
          <div className="feature-list">
            <article className="feature">
              <span className="tag feature__num">01</span>
              <div>
                <h3>Coupes intelligentes</h3>
                <p>Détecte silences, erreurs et temps morts.</p>
              </div>
            </article>
            <article className="feature feature--dark">
              <span className="tag feature__num">02</span>
              <div>
                <h3>Sous-titres automatiques</h3>
                <p>Génère des sous-titres synchronisés et propres.</p>
              </div>
            </article>
            <article className="feature">
              <span className="tag feature__num">03</span>
              <div>
                <h3>Recadrage intelligent</h3>
                <p>Un montage. Tous les formats.</p>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section className="section" id="fonctionnement">
        <div className="container">
          <div className="section__head">
            <span className="tag">03 | Comment ça marche</span>
          </div>
          <h2 className="title">
            Une vidéo. Un moteur.
            <br />
            Un montage final.
          </h2>
          <div className="steps">
            <article className="step">
              <span className="tag">01</span>
              <h3>Importer</h3>
              <p>Déposez vos rushs.</p>
            </article>
            <article className="step">
              <span className="tag">02</span>
              <h3>Analyser</h3>
              <p>L’IA comprend votre histoire.</p>
            </article>
            <article className="step step--dark">
              <span className="tag">03</span>
              <h3>Monter</h3>
              <p>Coupe, sous-titre, recadre.</p>
            </article>
            <article className="step">
              <span className="tag">04</span>
              <h3>Exporter</h3>
              <p>Publiez en quelques minutes.</p>
            </article>
          </div>
        </div>
      </section>

      <section className="section" id="statut">
        <div className="container">
          <div className="section__head">
            <span className="tag">04 | Système de statut</span>
          </div>
          <h2 className="title">
            Chaque processus
            <br />a son signal.
          </h2>
          <ul className="signals">
            <li>
              <div>
                <span className="signal__name">
                  <i className="dot dot--green" />
                  Succès
                </span>
                <p>Montage terminé avec succès</p>
              </div>
              <span className="tag signal__state">
                <i className="dot dot--ink" />
                Actif
              </span>
            </li>
            <li>
              <div>
                <span className="signal__name">
                  <i className="dot dot--yellow" />
                  Traitement
                </span>
                <p>Analyse et montage en cours</p>
              </div>
              <span className="tag signal__state">
                <i className="dot dot--ink" />
                Actif
              </span>
            </li>
            <li>
              <div>
                <span className="signal__name">
                  <i className="dot dot--red" />
                  Erreur
                </span>
                <p>Un problème est survenu.</p>
              </div>
              <span className="tag signal__state">
                <i className="dot dot--ink" />
                Actif
              </span>
            </li>
          </ul>
        </div>
      </section>

      <section className="section section--dark" id="vitesse">
        <div className="container">
          <div className="section__head">
            <span className="tag">05 | Conçu pour la vitesse</span>
          </div>
          <div className="stats">
            <div className="stats__items">
              <div className="stat">
                <span className="stat__value">10×</span>
                <span className="tag">Premiers montages plus rapides</span>
              </div>
              <div className="stat">
                <span className="stat__value">4K</span>
                <span className="tag">Qualité d’export</span>
              </div>
              <div className="stat">
                <span className="stat__value">01</span>
                <span className="tag">Éditeur dont vous avez besoin</span>
              </div>
            </div>
            <p className="stats__note">
              Pensé pour les créateurs, les équipes et tous ceux qui veulent itérer — pas la timeline.
            </p>
          </div>
        </div>
      </section>

      <section className="section" id="commencer">
        <div className="container">
          <div className="section__head">
            <span className="tag">06 | Commencer</span>
          </div>
          <h2 className="title cta__title">
            Votre prochaine vidéo
            <br />
            commence ici.
          </h2>
          <a className="btn btn--dark" href="#/inscription">
            Créer ma première vidéo
            <ArrowRight size={15} />
          </a>
        </div>
      </section>

      <footer className="footer">
        <div className="container footer__row">
          <span className="tag">AutoCut / Montage vidéo automatique / 2026</span>
          <span className="tag footer__status">
            <i className="dot dot--green" />
            Statut — tous les systèmes opérationnels
          </span>
        </div>
      </footer>
    </div>
  )
}
