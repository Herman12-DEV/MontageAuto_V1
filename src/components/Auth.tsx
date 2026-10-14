import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { showToast } from './Toast'
import { refreshUser } from '../api'
import {
  authErrorMessage,
  loginWithGoogle,
  loginWithPassword,
  registerWithUsername,
  sendReset,
} from '../lib/authActions'

type AuthMode = 'inscription' | 'connexion'

const copy: Record<AuthMode, { step: string; title: string; text: string }> = {
  inscription: {
    step: 'Inscription',
    title: 'Créez votre compte',
    text: 'Choisissez un nom d’utilisateur et un mot de passe : vous êtes connecté immédiatement.',
  },
  connexion: {
    step: 'Connexion',
    title: 'Bon retour.',
    text: 'Retrouvez vos projets et continuez votre montage.',
  },
}

function goToApp() {
  let next = '#/app'
  try {
    next = window.sessionStorage.getItem('autocut.next') || next
    window.sessionStorage.removeItem('autocut.next')
  } catch {
    // stockage indisponible
  }
  window.location.hash = next
}

function GoogleLogo() {
  return (
    <svg width="15" height="15" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  )
}

export default function Auth({ mode }: { mode: AuthMode }) {
  const inscription = mode === 'inscription'
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  useEffect(() => {
    setError('')
  }, [mode])

  // Après connexion Firebase : chargement (ou création) du compte AutoCut côté serveur.
  const finish = async (welcome: string) => {
    const user = await refreshUser()
    showToast(welcome.replace('{name}', user.name))
    goToApp()
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setPending(true)
    try {
      if (inscription) {
        await registerWithUsername(identifier, password)
        await finish('Bienvenue {name} — vos 2 montages gratuits vous attendent.')
      } else {
        await loginWithPassword(identifier, password)
        await finish('Connexion réussie — redirection vers vos projets.')
      }
    } catch (err) {
      setError(authErrorMessage(err))
    } finally {
      setPending(false)
    }
  }

  const google = async () => {
    setError('')
    setPending(true)
    try {
      await loginWithGoogle()
      await finish('Connexion réussie — bienvenue {name}.')
    } catch (err) {
      setError(authErrorMessage(err))
    } finally {
      setPending(false)
    }
  }

  const forgotPassword = async () => {
    setError('')
    if (!identifier) {
      setError('Saisissez votre adresse e-mail ci-dessus, puis cliquez à nouveau sur « Mot de passe oublié ? ».')
      return
    }
    try {
      await sendReset(identifier)
      showToast('Si un compte existe pour cet e-mail, un lien de réinitialisation vient d’être envoyé.')
    } catch (err) {
      setError(authErrorMessage(err))
    }
  }

  const text = copy[mode]

  return (
    <div className="auth">
      <div className="container auth__top">
        <a className="brand" href="#/">
          AutoCut
        </a>
        <span className="tag">01 | {text.step}</span>
      </div>
      <div className="container auth__grid">
        <div className="auth__copy">
          <h1>{text.title}</h1>
          <p>{text.text}</p>
        </div>
        <form className="card auth__form" onSubmit={handleSubmit}>
          {mode === 'connexion' && (
            <div className="auth__badge-row">
              <span className="pill pill--green">Connexion</span>
              <p>Récupérez votre espace AutoCut.</p>
            </div>
          )}
          <button type="button" className="btn btn--white btn--block" onClick={google} disabled={pending}>
            <GoogleLogo />
            Continuer avec Google
          </button>
          <p className="tag auth__divider">ou avec vos identifiants</p>
          <label className="field">
            <span className="tag">{inscription ? 'Nom d’utilisateur' : 'Nom d’utilisateur ou e-mail'}</span>
            <input
              type="text"
              required
              minLength={inscription ? 3 : 1}
              maxLength={inscription ? 30 : 255}
              pattern={inscription ? '[A-Za-z0-9][A-Za-z0-9._\\-]{2,29}' : undefined}
              title={inscription ? '3 à 30 caractères : lettres, chiffres, point, tiret ou tiret bas.' : undefined}
              placeholder={inscription ? 'ex. awa.kone' : 'awa.kone'}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              value={identifier}
              onChange={(event) => setIdentifier(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="tag">Mot de passe</span>
            <input
              type="password"
              required
              minLength={8}
              placeholder={inscription ? '8 caractères minimum' : '••••••••'}
              autoComplete={inscription ? 'new-password' : 'current-password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error && (
            <p className="upload-error" role="alert">
              {error}
            </p>
          )}
          <button className="btn btn--green btn--block" type="submit" disabled={pending}>
            {pending ? 'Patientez…' : inscription ? 'Créer mon compte' : 'Se connecter'}
          </button>
          <p className="auth__alt">
            {inscription ? (
              <>
                J’ai déjà un compte ? <a href="#/connexion">Se connecter</a>
              </>
            ) : (
              <>
                <button type="button" className="link" onClick={forgotPassword}>
                  Mot de passe oublié ?
                </button>
                {' · '}
                <a href="#/inscription">Créer un compte</a>
              </>
            )}
          </p>
          {inscription && (
            <p className="auth__alt">
              En créant un compte, vous acceptez les <a href="#/cgu">CGU</a> et la{' '}
              <a href="#/confidentialite">politique de confidentialité</a>.
            </p>
          )}
        </form>
      </div>
    </div>
  )
}
