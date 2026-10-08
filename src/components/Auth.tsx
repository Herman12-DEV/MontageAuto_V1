import type { FormEvent } from 'react'
import { showToast } from './Toast'

type AuthMode = 'inscription' | 'connexion'

export default function Auth({ mode }: { mode: AuthMode }) {
  const inscription = mode === 'inscription'

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    showToast(
      inscription
        ? 'Compte créé — bienvenue sur AutoCut.'
        : 'Connexion réussie — redirection vers vos projets.',
    )
    window.location.hash = '#/app'
  }

  return (
    <div className="auth">
      <div className="container auth__top">
        <span className="brand">AutoCut</span>
        <span className="tag">01 | {inscription ? 'Inscription' : 'Connexion'}</span>
      </div>
      <div className="container auth__grid">
        <div className="auth__copy">
          <h1>{inscription ? 'Créez votre compte' : 'Bon retour.'}</h1>
          <p>
            {inscription
              ? 'Commencez à transformer vos vidéos avec l’IA.'
              : 'Retrouvez vos projets et continuez votre montage.'}
          </p>
        </div>
        <form className="card auth__form" onSubmit={handleSubmit}>
          {!inscription && (
            <div className="auth__badge-row">
              <span className="pill pill--green">Connexion</span>
              <p>Récupérez votre espace AutoCut.</p>
            </div>
          )}
          <label className="field">
            <span className="tag">Email</span>
            <input type="email" required placeholder="vous@exemple.com" autoComplete="email" />
          </label>
          <label className="field">
            <span className="tag">Mot de passe</span>
            <input
              type="password"
              required
              minLength={8}
              placeholder="••••••••"
              autoComplete={inscription ? 'new-password' : 'current-password'}
            />
          </label>
          <button className="btn btn--green btn--block" type="submit">
            {inscription ? 'Créer mon compte' : 'Se connecter'}
          </button>
          <p className="auth__alt">
            {inscription ? (
              <>
                J’ai déjà un compte ? <a href="#/connexion">Se connecter</a>
              </>
            ) : (
              <button
                type="button"
                className="link"
                onClick={() => showToast('Lien de réinitialisation envoyé — démo 100 % front.')}
              >
                Mot de passe oublié ?
              </button>
            )}
          </p>
        </form>
      </div>
    </div>
  )
}
