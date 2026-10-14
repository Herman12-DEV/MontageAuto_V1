import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRight, Pencil } from 'lucide-react'
import { showToast } from './Toast'
import { creditsLabel } from './AppLayout'
import { api, clearSession, deleteAllStoredFiles, errorMessage, formatDate, refreshUser, setUser, useUser } from '../api'
import { auth } from '../lib/firebase'
import {
  authErrorMessage,
  canChangePassword,
  changeDisplayName,
  changePassword,
  confirmIdentity,
  deleteCurrentUser,
  signInMethods,
} from '../lib/authActions'
import type { User } from '../api'

const planDetails: Record<User['plan'], string> = {
  free: '2 montages par mois • Vidéos jusqu’à 5 min • Filigrane',
  pro: 'Montages illimités • Vidéos jusqu’à 30 min • Sans filigrane • File prioritaire',
  agence: 'Montages illimités • Traitement par lot • Sans filigrane • Support prioritaire',
}

export default function Profile({ params }: { params: URLSearchParams }) {
  const user = useUser()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [pwOpen, setPwOpen] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [pwError, setPwError] = useState('')
  const payment = params.get('paiement')

  useEffect(() => {
    if (payment === 'ok') {
      showToast('Paiement confirmé — votre offre est active.')
      // Le webhook Stripe peut arriver une seconde après la redirection.
      refreshUser().catch(() => undefined)
      const timer = window.setTimeout(() => refreshUser().catch(() => undefined), 2500)
      return () => window.clearTimeout(timer)
    }
    if (payment === 'annule') showToast('Paiement annulé — aucun débit effectué.')
  }, [payment])

  if (!user) return <p className="tag analysis__hint">Chargement…</p>

  const startEdit = () => {
    setName(user.name)
    setEmail(user.email ?? '')
    setEditing(true)
  }

  const saveProfile = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    try {
      setUser(await api<User>('/api/me', { method: 'PATCH', body: { name, email: email.trim() } }))
      await changeDisplayName(name).catch(() => undefined)
      setEditing(false)
      showToast('Profil mis à jour.')
    } catch (err) {
      showToast(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const subscribe = async (plan: 'pro' | 'agence') => {
    setBusy(true)
    try {
      const res = await api<{ url: string | null; activated: boolean; user: User }>('/api/billing/checkout', {
        body: { plan },
      })
      if (res.url) {
        window.location.href = res.url // page de paiement sécurisée Stripe
        return
      }
      setUser(res.user)
      showToast('Offre activée — merci !')
    } catch (err) {
      showToast(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const manage = async () => {
    try {
      const res = await api<{ url: string }>('/api/billing/portal', { method: 'POST' })
      window.location.href = res.url
    } catch (err) {
      showToast(errorMessage(err))
    }
  }

  const exportData = async () => {
    try {
      const data = await api<unknown>('/api/me/export')
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = 'mes-donnees-autocut.json'
      link.click()
      URL.revokeObjectURL(link.href)
    } catch (err) {
      showToast(errorMessage(err))
    }
  }

  const deleteAccount = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      // 1. Confirmation d'identité Firebase (mot de passe ou nouvelle connexion Google).
      await confirmIdentity(withPassword ? password : undefined)
      // 2. Vidéos importées dans Firebase Storage.
      const uid = auth.currentUser?.uid
      if (uid) await deleteAllStoredFiles(uid).catch(() => undefined)
      // 3. Données du serveur (compte, montages, rendus).
      await api('/api/me', { method: 'DELETE', body: { password: user.username ?? '' } })
      // 4. Compte Firebase lui-même.
      await deleteCurrentUser()
      await clearSession().catch(() => undefined)
      showToast('Compte supprimé. Toutes vos données ont été effacées.')
      window.location.hash = '#/'
    } catch (err) {
      setError(err instanceof Error && 'code' in err ? authErrorMessage(err) : errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const savePassword = async (event: FormEvent) => {
    event.preventDefault()
    setPwError('')
    try {
      await changePassword(currentPassword, newPassword)
      setCurrentPassword('')
      setNewPassword('')
      setPwOpen(false)
      showToast('Mot de passe modifié.')
    } catch (err) {
      setPwError(authErrorMessage(err))
    }
  }

  const quota = user.quota
  const withPassword = canChangePassword()
  const paid = user.plan !== 'free'

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
          <button className="btn btn--white" onClick={startEdit}>
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
          {editing ? (
            <form className="profile-fields" onSubmit={saveProfile}>
              <label className="field">
                <span className="tag">Nom</span>
                <input value={name} onChange={(event) => setName(event.target.value)} required maxLength={120} />
              </label>
              <label className="field">
                <span className="tag">E-mail (facultatif — pour récupérer votre mot de passe)</span>
                <input
                  type="email"
                  value={email}
                  placeholder="vous@exemple.com"
                  autoComplete="email"
                  disabled={user.google_linked}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </label>
              <div className="page-head__actions">
                <button className="btn btn--green btn--sm" type="submit" disabled={busy}>
                  Enregistrer
                </button>
                <button className="btn btn--ghost btn--sm" type="button" onClick={() => setEditing(false)}>
                  Annuler
                </button>
              </div>
            </form>
          ) : (
            <dl className="profile-fields">
              <div>
                <dt className="tag">Nom</dt>
                <dd>{user.name}</dd>
              </div>
              <div>
                <dt className="tag">Nom d’utilisateur</dt>
                <dd>{user.username}</dd>
              </div>
              <div>
                <dt className="tag">Email</dt>
                <dd>{user.email ?? 'Aucun — ajoutez-en un pour pouvoir récupérer votre mot de passe'}</dd>
              </div>
              <div>
                <dt className="tag">Connexion</dt>
                <dd>
                  {signInMethods().join(' · ') || '—'}
                </dd>
              </div>
              <div>
                <dt className="tag">Membre depuis</dt>
                <dd>{formatDate(user.created_at)}</dd>
              </div>
            </dl>
          )}
          {!editing && (
            <button className="btn btn--ghost btn--sm" onClick={startEdit}>
              Modifier
            </button>
          )}
          <hr className="divider" />
          {withPassword && (
            <>
              <dl className="profile-fields">
                <div>
                  <dt className="tag">Sécurité</dt>
                  <dd>
                    <button type="button" className="link" onClick={() => setPwOpen((v) => !v)}>
                      Changer mon mot de passe
                    </button>
                  </dd>
                </div>
              </dl>
              {pwOpen && (
                <form className="profile-fields" onSubmit={savePassword}>
                  <label className="field">
                    <span className="tag">Mot de passe actuel</span>
                    <input
                      type="password"
                      required
                      autoComplete="current-password"
                      value={currentPassword}
                      onChange={(event) => setCurrentPassword(event.target.value)}
                    />
                  </label>
                  <label className="field">
                    <span className="tag">Nouveau mot de passe</span>
                    <input
                      type="password"
                      required
                      minLength={8}
                      autoComplete="new-password"
                      value={newPassword}
                      onChange={(event) => setNewPassword(event.target.value)}
                    />
                  </label>
                  {pwError && <p className="upload-error">{pwError}</p>}
                  <button className="btn btn--green btn--sm" type="submit">
                    Enregistrer le mot de passe
                  </button>
                </form>
              )}
              <hr className="divider" />
            </>
          )}
          <dl className="profile-fields">
            <div>
              <dt className="tag">Mes données</dt>
              <dd>
                <button type="button" className="link" onClick={exportData}>
                  Télécharger mes données
                </button>
                {' · '}
                <button type="button" className="link" onClick={() => setDeleting((v) => !v)}>
                  Supprimer mon compte
                </button>
              </dd>
            </div>
          </dl>
          {deleting && (
            <form className="profile-fields" onSubmit={deleteAccount}>
              <p className="upload-error">
                Suppression définitive du compte, de toutes vos vidéos et de votre abonnement. Cette action est
                irréversible.
              </p>
              {withPassword ? (
                <label className="field">
                  <span className="tag">Confirmez avec votre mot de passe</span>
                  <input
                    type="password"
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                </label>
              ) : (
                <p className="plan-sub">Une fenêtre Google s’ouvrira pour confirmer votre identité.</p>
              )}
              {error && <p className="upload-error">{error}</p>}
              <button className="btn btn--ghost btn--sm" type="submit" disabled={busy}>
                Supprimer définitivement
              </button>
            </form>
          )}
        </section>
        <section className="card profile-card">
          <div className="card__head">
            <span className="tag">Abonnement</span>
            <span className="pill pill--green">Actif</span>
          </div>
          <div>
            <p className="plan-name">{quota.plan_label}</p>
            <p className="plan-sub">{planDetails[user.plan]}</p>
          </div>
          <div>
            <span className="tag">Crédits</span>
            <p className="plan-name">{creditsLabel(quota)}</p>
          </div>
          <hr className="divider" />
          <div>
            <span className="tag">{paid ? 'Prochain renouvellement' : 'Passez à la vitesse supérieure'}</span>
            <p className="plan-name">{paid ? formatDate(user.plan_renews_at) : 'Plan Pro · 7 €/mois'}</p>
            {!paid && <p className="plan-sub">{planDetails.pro}</p>}
          </div>
          {paid ? (
            user.has_subscription && (
              <button className="btn btn--ghost btn--block" onClick={manage}>
                Gérer mon abonnement
              </button>
            )
          ) : (
            <button className="btn btn--green btn--block" onClick={() => subscribe('pro')} disabled={busy}>
              Passer au plan Pro
            </button>
          )}
          {user.plan !== 'agence' && (
            <button className="btn btn--ghost btn--block" onClick={() => subscribe('agence')} disabled={busy}>
              Offre Agence · 29 €/mois
            </button>
          )}
        </section>
      </div>
    </>
  )
}
