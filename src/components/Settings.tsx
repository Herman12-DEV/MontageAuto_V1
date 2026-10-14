import { useEffect, useState } from 'react'
import { showToast } from './Toast'
import { api, errorMessage, getLibrary, setUser, useUser } from '../api'
import type { Library, Prefs, User } from '../api'

type ToggleKey = 'notify_email' | 'theme' | 'auto_analyse'

type Setting = {
  key: ToggleKey
  label: string
  description: string
}

const toggles: Setting[] = [
  {
    key: 'notify_email',
    label: 'Notifications par email',
    description: 'Recevez un email à chaque montage terminé.',
  },
  {
    key: 'theme',
    label: 'Thème sombre',
    description: 'L’interface AutoCut reste toujours en thème sombre.',
  },
  {
    key: 'auto_analyse',
    label: 'Analyse automatique',
    description: 'Lance l’analyse dès le dépôt d’une vidéo.',
  },
]

export default function Settings() {
  const user = useUser()
  const [library, setLibrary] = useState<Library | null>(null)

  useEffect(() => {
    getLibrary().then(setLibrary).catch(() => undefined)
  }, [])

  const save = async (changes: Partial<Prefs>) => {
    if (!user) return
    // Mise à jour optimiste : l’interrupteur réagit immédiatement.
    setUser({ ...user, prefs: { ...user.prefs, ...changes } })
    try {
      setUser(await api<User>('/api/me', { method: 'PATCH', body: { prefs: changes } }))
    } catch (err) {
      setUser(user)
      showToast(errorMessage(err))
    }
  }

  if (!user) return <p className="tag analysis__hint">Chargement…</p>

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="page-title">Réglages.</h1>
          <p className="page-sub">Personnalisez votre espace AutoCut.</p>
        </div>
      </header>
      <div className="settings-list">
        {toggles.map((setting) => {
          const checked = setting.key === 'theme' ? true : user.prefs[setting.key]
          return (
            <div className="setting" key={setting.key}>
              <div>
                <h3>{setting.label}</h3>
                <p>
                  {setting.key === 'notify_email' && !user.email
                    ? 'Ajoutez une adresse e-mail dans « Mon profil » pour recevoir ces notifications.'
                    : setting.description}
                </p>
              </div>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={setting.key === 'theme'}
                  onChange={() => setting.key !== 'theme' && save({ [setting.key]: !checked })}
                  aria-label={setting.label}
                />
                <i />
              </label>
            </div>
          )
        })}
        {library && (
          <>
            <div className="setting">
              <div>
                <h3>Style de sous-titres par défaut</h3>
                <p>Proposé automatiquement à chaque nouveau montage.</p>
              </div>
              <select
                className="setting__select"
                value={user.prefs.subtitle_style}
                onChange={(event) => save({ subtitle_style: event.target.value })}
                aria-label="Style de sous-titres par défaut"
              >
                {library.styles.map((style) => (
                  <option key={style.key} value={style.key}>
                    {style.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="setting">
              <div>
                <h3>Format par défaut</h3>
                <p>Vertical pour TikTok, Reels et Shorts ; carré ou d’origine sinon.</p>
              </div>
              <select
                className="setting__select"
                value={user.prefs.format}
                onChange={(event) => save({ format: event.target.value as Prefs['format'] })}
                aria-label="Format par défaut"
              >
                {library.formats.map((format) => (
                  <option key={format.key} value={format.key}>
                    {format.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="setting">
              <div>
                <h3>Langue des vidéos</h3>
                <p>La détection automatique reconnaît le français et l’anglais.</p>
              </div>
              <select
                className="setting__select"
                value={user.prefs.language}
                onChange={(event) => save({ language: event.target.value as Prefs['language'] })}
                aria-label="Langue des vidéos"
              >
                {library.languages.map((language) => (
                  <option key={language.key} value={language.key}>
                    {language.label}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}
      </div>
    </>
  )
}
