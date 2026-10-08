import { useState } from 'react'

type Setting = {
  label: string
  description: string
  value: boolean
}

const initialSettings: Setting[] = [
  {
    label: 'Notifications par email',
    description: 'Recevez un email à chaque montage terminé.',
    value: true,
  },
  {
    label: 'Thème sombre',
    description: 'L’interface AutoCut reste toujours en thème sombre.',
    value: true,
  },
  {
    label: 'Analyse automatique',
    description: 'Lance l’analyse dès le dépôt d’une vidéo.',
    value: false,
  },
]

export default function Settings() {
  const [settings, setSettings] = useState(initialSettings)

  const toggle = (index: number) => {
    setSettings((current) =>
      current.map((setting, i) => (i === index ? { ...setting, value: !setting.value } : setting)),
    )
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="page-title">Réglages.</h1>
          <p className="page-sub">Personnalisez votre espace AutoCut.</p>
        </div>
      </header>
      <div className="settings-list">
        {settings.map((setting, index) => (
          <div className="setting" key={setting.label}>
            <div>
              <h3>{setting.label}</h3>
              <p>{setting.description}</p>
            </div>
            <label className="switch">
              <input
                type="checkbox"
                checked={setting.value}
                onChange={() => toggle(index)}
                aria-label={setting.label}
              />
              <i />
            </label>
          </div>
        ))}
      </div>
    </>
  )
}
