export default function SiteFooter() {
  return (
    <footer className="footer">
      <div className="container footer__row">
        <span className="tag">AutoCut / Montage vidéo automatique / 2026</span>
        <nav className="footer__links">
          <a className="tag" href="#/tarifs">
            Tarifs
          </a>
          <a className="tag" href="#/faq">
            FAQ
          </a>
          <a className="tag" href="#/mentions-legales">
            Mentions légales
          </a>
          <a className="tag" href="#/confidentialite">
            Confidentialité
          </a>
          <a className="tag" href="#/cgu">
            CGU
          </a>
        </nav>
        <span className="tag footer__status">
          <i className="dot dot--green" />
          Statut — tous les systèmes opérationnels
        </span>
      </div>
    </footer>
  )
}
