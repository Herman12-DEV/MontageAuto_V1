import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Clock3,
  Clapperboard,
  CloudUpload,
  Download,
  FileVideo2,
  FolderOpen,
  LockKeyhole,
  Mail,
  MonitorPlay,
  MoreHorizontal,
  Play,
  Plus,
  Scissors,
  Settings2,
  ShieldCheck,
  Sparkles,
  Upload,
  UserRound,
  X,
} from 'lucide-react'

type Screen = 'landing' | 'signup' | 'login' | 'projects' | 'new' | 'result' | 'profile'
type Project = { title: string; date: string; length: string; status: 'TERMINE' | 'EN COURS' | 'ERREUR'; palette: string }

const projects: Project[] = [
  { title: 'CAMPAGNE ÉTÉ', date: 'Aujourd’hui · 09:24', length: '02:14', status: 'TERMINE', palette: 'thumb-sand' },
  { title: 'REEL PRODUIT', date: 'Aujourd’hui · 08:16', length: '00:34', status: 'EN COURS', palette: 'thumb-green' },
  { title: 'INTERVIEW CLIENT', date: 'Hier · 17:42', length: '06:21', status: 'ERREUR', palette: 'thumb-red' },
]

const formats = ['9:16', '1:1', '16:9']
const processSteps = ['DÉTECTION DES SILENCES', 'COUPES', 'SOUS-TITRES', 'RECADRAGE']

function App() {
  const [screen, setScreen] = useState<Screen>('landing')
  const [file, setFile] = useState<File | null>(null)
  const [fileName, setFileName] = useState('')
  const [sourceMode, setSourceMode] = useState<'fichier' | 'youtube'>('fichier')
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [format, setFormat] = useState('9:16')
  const [language, setLanguage] = useState('Automatique')
  const [style, setStyle] = useState('Karaoké')
  const [music, setMusic] = useState(true)
  const [progress, setProgress] = useState(0)
  const [processing, setProcessing] = useState(false)
  const [toast, setToast] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const notify = useCallback((message: string) => setToast(message), [])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(''), 3200)
    return () => window.clearTimeout(timer)
  }, [toast])

  useEffect(() => {
    if (!processing) return
    const timer = window.setInterval(() => setProgress((current) => Math.min(100, current + 4)), 180)
    return () => window.clearInterval(timer)
  }, [processing])

  useEffect(() => {
    if (!processing || progress < 100) return
    setProcessing(false)
    setScreen('result')
    notify('Parcours de démonstration terminé. Le rendu vidéo réel reste à connecter.')
  }, [processing, progress, notify])

  const handleFile = (newFile?: File) => {
    if (!newFile) return
    const extension = newFile.name.split('.').pop()?.toLowerCase() ?? ''
    const allowed = ['mp4', 'mov', 'webm', 'mkv'].includes(extension)
    const videoMime = newFile.type === '' || newFile.type.startsWith('video/') || newFile.type === 'application/octet-stream'
    if (!allowed || !videoMime) {
      setUploadError('Format non pris en charge. Choisissez un fichier MP4, MOV, WebM ou MKV valide.')
      return
    }
    if (newFile.size > 500 * 1024 * 1024) {
      setUploadError('Le fichier dépasse la limite de 500 Mo.')
      return
    }
    setFile(newFile)
    setFileName(newFile.name)
    setUploadError('')
    setProgress(0)
    notify('Fichier ajouté au prototype local.')
  }

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.currentTarget.classList.remove('drag-active')
    handleFile(event.dataTransfer.files?.[0])
  }

  const clearFile = () => {
    setFile(null)
    setFileName('')
    setProgress(0)
    setUploadError('')
    if (inputRef.current) inputRef.current.value = ''
  }

  const beginProcessing = () => {
    if (sourceMode === 'fichier' && !file) {
      setUploadError('Ajoutez une vidéo avant de lancer le montage.')
      return
    }
    if (sourceMode === 'youtube' && !/^https?:\/\/(www\.)?(youtube\.com|youtu\.be)\//i.test(youtubeUrl.trim())) {
      setUploadError('Saisissez une URL YouTube valide.')
      return
    }
    if (sourceMode === 'youtube') setFileName('Import YouTube · démo')
    setUploadError('')
    setProgress(0)
    setProcessing(true)
  }

  const navigate = (next: Screen) => {
    setScreen(next)
    if (next === 'new') {
      setProgress(0)
      setProcessing(false)
    }
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="site-root">
      {screen === 'landing' && <LandingPage onStart={() => navigate('signup')} onLogin={() => navigate('login')} />}
      {(screen === 'signup' || screen === 'login') && <AuthPage mode={screen} onSwitch={navigate} onSuccess={() => { navigate('projects'); notify('Bienvenue dans la démonstration MontageAuto.') }} />}
      {screen === 'projects' && (
        <WorkspaceShell active="projects" onNavigate={navigate}>
          <ProjectsPage onNew={() => navigate('new')} onOpen={() => navigate('result')} onToast={notify} />
        </WorkspaceShell>
      )}
      {screen === 'new' && (
        <WorkspaceShell active="new" onNavigate={navigate}>
          <NewProjectPage
            file={file}
            fileName={fileName}
            sourceMode={sourceMode}
            youtubeUrl={youtubeUrl}
            error={uploadError}
            format={format}
            language={language}
            style={style}
            music={music}
            progress={progress}
            processing={processing}
            inputRef={inputRef}
            onFile={handleFile}
            onDrop={handleDrop}
            onClear={clearFile}
            onSourceMode={(mode) => { setSourceMode(mode); setUploadError('') }}
            onYoutubeChange={setYoutubeUrl}
            onFormat={setFormat}
            onLanguage={setLanguage}
            onStyle={setStyle}
            onMusic={setMusic}
            onStart={beginProcessing}
            onCancel={() => navigate('projects')}
          />
        </WorkspaceShell>
      )}
      {screen === 'result' && (
        <WorkspaceShell active="projects" onNavigate={navigate}>
          <ResultPage fileName={fileName || 'CAMPAGNE_ETE.mp4'} format={format} onNew={() => navigate('new')} onToast={notify} />
        </WorkspaceShell>
      )}
      {screen === 'profile' && (
        <WorkspaceShell active="profile" onNavigate={navigate}>
          <ProfilePage onToast={notify} onNew={() => navigate('new')} />
        </WorkspaceShell>
      )}
      {toast && <div className="toast" role="status" aria-live="polite"><CheckCircle2 size={16} />{toast}</div>}
    </div>
  )
}

function Brand({ light = true, onClick }: { light?: boolean; onClick?: () => void }) {
  return <button className={`brand${light ? ' brand-light' : ' brand-dark'}`} onClick={onClick} aria-label="MontageAuto, accueil"><span className="brand-symbol"><Clapperboard size={16} /></span><span>MONTAGEAUTO</span></button>
}

function LandingPage({ onStart, onLogin }: { onStart: () => void; onLogin: () => void }) {
  return (
    <div className="landing-page">
      <section className="landing-hero" id="produit">
        <header className="landing-nav">
          <Brand onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} />
          <span className="landing-code">MONTAGE VIDÉO AUTOMATIQUE / 01</span>
          <nav><a href="#produit">PRODUIT</a><a href="#fonctionnement">FONCTIONNEMENT</a><a href="#tarifs">TARIFS</a><button onClick={onLogin}>CONNEXION</button></nav>
        </header>
        <div className="hero-main">
          <div className="hero-copy">
            <p className="hero-kicker"><span /> LE MONTAGE VIDÉO, AUTREMENT</p>
            <h1>MONTEZ<br />MOINS.<br /><span>PUBLIEZ PLUS.</span></h1>
            <p className="hero-description">Transformez vos rushs en vidéos prêtes à publier.<br />Coupez. Sous-titrez. Recadrez. Exportez.</p>
            <button className="button-white" onClick={onStart}>COMMENCER À CRÉER <ArrowRight size={14} /></button>
            <p className="hero-note">Pas de timeline. Pas de travail répétitif. Juste le montage final.</p>
            <span className="live-engine"><i /> MOTEUR EN LIGNE</span>
          </div>
          <div className="hero-demo-window">
            <div className="demo-window-header"><div className="window-dots"><i /><i /><i /></div><span>PROJET : CAMPAGNE_ÉTÉ</span><MoreHorizontal size={15} /></div>
            <div className="demo-window-body">
              <span className="tiny-label">APERÇU DU MONTAGE</span>
              <div className="hero-demo-screen"><div className="hero-demo-person"><i /><b /></div><div className="hero-demo-caption">C'EST LE MOMENT<br /><strong>DE PUBLIER.</strong></div><div className="hero-demo-play"><Play size={15} fill="currentColor" /></div></div>
              <div className="demo-timeline"><span /><span /><span /><span /><span /></div>
              <div className="demo-audio-wave">{Array.from({ length: 28 }, (_, i) => <i key={i} style={{ height: `${6 + ((i * 7) % 15)}px` }} />)}</div>
              <div className="demo-window-footer"><span><CheckCircle2 size={12} /> SOUS-TITRES SYNCHRONISÉS</span><span>9:16 · 00:32</span></div>
            </div>
            <span className="demo-float-tag"><Sparkles size={12} /> MONTAGE AUTOMATIQUE</span>
          </div>
        </div>
        <div className="hero-bottom-line"><span>01 — CRÉATEURS, COACHS, ÉQUIPES</span><span>FAIT POUR PUBLIER. PAS POUR MONTER.</span><span>SCROLL POUR DÉCOUVRIR ↓</span></div>
      </section>

      <section className="manifesto section-cream" id="fonctionnement">
        <div className="manifesto-top"><span className="section-number">02 / LA PROMESSE</span><div className="manifesto-title"><h2>VOTRE VIDÉO,<br />SANS LA<br />TIMELINE.</h2><p>MontageAuto analyse vos rushs, comprend votre histoire et crée automatiquement un premier montage.</p></div><div className="thin-rule" /></div>
        <div className="feature-block">
          <h3>DES RUSHS<br />À LA PUBLICATION.</h3>
          <div className="feature-list">
            <FeatureRow number="01" title="COUPES INTELLIGENTES" text="Détecte les silences, erreurs et temps morts." />
            <FeatureRow number="02" title="SOUS-TITRES AUTOMATIQUES" text="Génère des sous-titres synchronisés et propres." inverse />
            <FeatureRow number="03" title="RECADRAGE INTELLIGENT" text="Un montage. Tous les formats." />
          </div>
        </div>
        <div className="process-block">
          <span className="section-number">03 / COMMENT ÇA MARCHE</span>
          <h3>UNE VIDÉO.<br />UN MOTEUR.<br />UN MONTAGE FINAL.</h3>
          <div className="process-cards">
            <ProcessCard number="01" title="IMPORTER" text="Déposez vos rushs." />
            <ProcessCard number="02" title="ANALYSER" text="L'IA comprend votre histoire." />
            <ProcessCard number="03" title="MONTER" text="Coupes, sous-titres, recadrage." inverse />
            <ProcessCard number="04" title="EXPORTER" text="Prêt à publier en quelques minutes." />
          </div>
        </div>
        <div className="status-block">
          <span className="section-number">04 / SYSTÈME DE STATUT</span>
          <h3>CHAQUE PROCESSUS<br />A SON SIGNAL.</h3>
          <div className="status-list"><StatusLine tone="green" label="SUCCÈS" text="Montage terminé avec succès" /><StatusLine tone="yellow" label="TRAITEMENT" text="Analyse et montage en cours" /><StatusLine tone="red" label="ERREUR" text="Un problème est survenu" /></div>
        </div>
      </section>

      <section className="spec-strip">
        <div><strong>≤ 3<span>MIN</span></strong><small>OBJECTIF POUR UN RUSH DE 10 MIN</small></div>
        <div><strong>3</strong><small>FORMATS DE SORTIE</small></div>
        <div><strong>01</strong><small>ÉDITEUR DONT VOUS AVEZ BESOIN</small></div>
        <p>Pensé pour les créateurs, les équipes et tous ceux qui veulent faire passer leur histoire — pas la timeline.</p>
      </section>

      <section className="landing-pricing section-cream" id="tarifs">
        <span className="section-number">05 / DES OFFRES SIMPLES</span>
        <h2>CRÉEZ À VOTRE RYTHME.</h2>
        <div className="landing-price-grid">
          <div><span>DÉCOUVERTE</span><strong>0 €</strong><p>2 vidéos / mois · avec filigrane</p><button onClick={onStart}>COMMENCER <ArrowRight size={13} /></button></div>
          <div className="landing-price-featured"><span>PRO</span><strong>7 €<small>/ mois</small></strong><p>Jusqu'à 30 min · sans filigrane</p><button onClick={onStart}>ESSAYER GRATUITEMENT <ArrowRight size={13} /></button></div>
          <div><span>AGENCE</span><strong>29 €<small>/ mois</small></strong><p>3 sièges · traitement par lot</p><button onClick={onStart}>DÉCOUVRIR <ArrowRight size={13} /></button></div>
        </div>
      </section>

      <section className="landing-cta">
        <span className="section-number">06 / COMMENCER</span>
        <h2>VOTRE PROCHAINE VIDÉO<br />COMMENCE ICI.</h2>
        <button className="button-black" onClick={onStart}>CRÉER MA PREMIÈRE VIDÉO <ArrowRight size={14} /></button>
      </section>
      <footer className="landing-footer"><Brand onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} /><span>© 2026 MONTAGEAUTO · MONTAGE VIDÉO AUTOMATIQUE</span><span>STATUT <i /> TOUS LES SYSTÈMES OPÉRATIONNELS</span></footer>
    </div>
  )
}

function FeatureRow({ number, title, text, inverse = false }: { number: string; title: string; text: string; inverse?: boolean }) {
  return <article className={`feature-row${inverse ? ' feature-row-inverse' : ''}`}><span>{number}</span><div><h4>{title}</h4><p>{text}</p></div><ArrowUpRight size={16} /></article>
}

function ProcessCard({ number, title, text, inverse = false }: { number: string; title: string; text: string; inverse?: boolean }) {
  return <article className={`process-card${inverse ? ' process-card-inverse' : ''}`}><span>{number}</span><h4>{title}</h4><p>{text}</p></article>
}

function StatusLine({ tone, label, text }: { tone: string; label: string; text: string }) {
  return <div className="status-line"><span className={`status-icon status-${tone}`}>{tone === 'green' ? <Check size={13} /> : tone === 'yellow' ? <Clock3 size={13} /> : <CircleAlert size={13} />}</span><div><strong>{label}</strong><small>{text}</small></div><span className="status-active"><i />ACTIF</span></div>
}

function AuthPage({ mode, onSwitch, onSuccess }: { mode: 'signup' | 'login'; onSwitch: (screen: Screen) => void; onSuccess: () => void }) {
  const isSignup = mode === 'signup'
  return (
    <main className="auth-page">
      <header className="auth-nav"><Brand onClick={() => onSwitch('landing')} /><button onClick={() => onSwitch(isSignup ? 'login' : 'signup')}>{isSignup ? 'DÉJÀ INSCRIT ?' : 'NOUVEAU SUR MONTAGEAUTO ?'} <strong>{isSignup ? 'CONNEXION' : 'CRÉER UN COMPTE'}</strong></button></header>
      <div className="auth-content">
        <div className="auth-pitch"><span className="section-number">{isSignup ? '01 / REJOIGNEZ LE STUDIO' : '02 / VOTRE ESPACE'}</span><h1>{isSignup ? <>CRÉEZ VOTRE<br />COMPTE.</> : <>BON<br />RETOUR.</>}</h1><p>{isSignup ? 'Commencez à transformer vos vidéos avec l’IA.' : 'Retrouvez vos projets et continuez votre montage.'}</p><button className="auth-back" onClick={() => onSwitch('landing')}><ArrowLeft size={13} /> RETOUR AU SITE</button></div>
        <form className="auth-card" onSubmit={(event) => { event.preventDefault(); onSuccess() }}>
          <span className="auth-card-kicker">{isSignup ? 'NOUVEAU COMPTE' : 'CONNEXION'}</span>
          <label><span>EMAIL</span><div className="input-wrap"><Mail size={14} /><input type="email" placeholder="vous@exemple.com" required /></div></label>
          <label><span>MOT DE PASSE</span><div className="input-wrap"><LockKeyhole size={14} /><input type="password" placeholder="••••••••••" minLength={8} required /></div></label>
          {isSignup && <label className="terms-row"><input type="checkbox" required /><span>J'accepte les conditions d'utilisation et la politique de confidentialité.</span></label>}
          {!isSignup && <button className="forgot-password" type="button">Mot de passe oublié ?</button>}
          <button className="auth-submit" type="submit">{isSignup ? 'CRÉER MON COMPTE' : 'SE CONNECTER'} <ArrowRight size={13} /></button>
          <p className="auth-legal"><ShieldCheck size={12} /> Prototype local · vos données ne sont pas envoyées.</p>
        </form>
      </div>
      <div className="auth-footer"><span>MONTAGEAUTO / 2026</span><span>FRANÇAIS <ChevronDown size={12} /></span></div>
    </main>
  )
}

function WorkspaceShell({ active, onNavigate, children }: { active: 'projects' | 'new' | 'profile'; onNavigate: (screen: Screen) => void; children: React.ReactNode }) {
  return (
    <div className="workspace-shell">
      <aside className="workspace-sidebar">
        <Brand onClick={() => onNavigate('landing')} />
        <span className="workspace-sidebar-label">TABLEAU DE BORD</span>
        <nav className="workspace-nav">
          <button className={active === 'projects' ? 'selected' : ''} onClick={() => onNavigate('projects')}><FolderOpen size={15} />MES PROJETS</button>
          <button className={active === 'new' ? 'selected' : ''} onClick={() => onNavigate('new')}><Plus size={15} />NOUVEAU MONTAGE</button>
          <button onClick={() => onNavigate('profile')}><Settings2 size={15} />RÉGLAGES</button>
          <button className={active === 'profile' ? 'selected' : ''} onClick={() => onNavigate('profile')}><UserRound size={15} />MON PROFIL</button>
        </nav>
        <div className="sidebar-user"><span className="user-initials">AK</span><span><strong>Awa Koné</strong><small>OFFRE DÉCOUVERTE</small></span><MoreHorizontal size={15} /></div>
      </aside>
      <main className="workspace-main">
        <header className="workspace-header"><div className="mobile-brand"><Brand onClick={() => onNavigate('projects')} /></div><span className="workspace-breadcrumb">MONTAGEAUTO <i>/</i> {active === 'new' ? 'NOUVEAU MONTAGE' : active === 'profile' ? 'MON PROFIL' : 'MES PROJETS'}</span><span className="online-indicator"><i /> MOTEUR EN LIGNE</span></header>
        <div className="workspace-content">{children}</div>
      </main>
    </div>
  )
}

function ProjectsPage({ onNew, onOpen, onToast }: { onNew: () => void; onOpen: () => void; onToast: (message: string) => void }) {
  return (
    <div className="app-page">
      <div className="page-title-row"><div><span className="section-number">VOTRE BIBLIOTHÈQUE</span><h1>VOS MONTAGES</h1><p>Créez, suivez et exportez vos vidéos.</p></div><button className="green-button" onClick={onNew}><Plus size={13} /> NOUVEAU MONTAGE</button></div>
      <div className="project-toolbar"><span>MES PROJETS <i>03</i></span><button onClick={() => onToast('Filtres disponibles dans la version complète.')}><Settings2 size={13} /> FILTRER <ChevronDown size={12} /></button></div>
      <div className="project-grid">{projects.map((project) => <ProjectCard key={project.title} project={project} onOpen={onOpen} onToast={onToast} />)}<button className="add-project-card" onClick={onNew}><span><Plus size={19} /></span><strong>NOUVEAU MONTAGE</strong><small>Déposez une vidéo pour commencer.</small></button></div>
      <div className="workspace-footnote"><LockKeyhole size={12} />Vos vidéos sont privées. Conservation prévue pendant 30 jours.</div>
    </div>
  )
}

function ProjectCard({ project, onOpen, onToast }: { project: Project; onOpen: () => void; onToast: (message: string) => void }) {
  const statusClass = project.status === 'TERMINE' ? 'project-status-done' : project.status === 'EN COURS' ? 'project-status-running' : 'project-status-error'
  return <article className="project-card"><button className={`project-preview ${project.palette}`} onClick={onOpen} aria-label={`Ouvrir ${project.title}`}><span className="preview-bars"><i /><i /><i /><i /></span><span className="preview-play"><Play size={15} fill="currentColor" /></span><span className="preview-watermark">M.</span></button><div className="project-card-content"><div className="project-card-title"><div><h3>{project.title}</h3><p>Ajouté · {project.date}</p></div><button className="more-button" aria-label="Actions du projet" onClick={() => onToast('Actions du projet disponibles après connexion du backend.')}><MoreHorizontal size={16} /></button></div><div className="project-card-meta"><span>APRÈS MONTAGE · {project.length}</span><span className={`project-status ${statusClass}`}><i />{project.status}</span></div></div></article>
}

function NewProjectPage({ file, fileName, sourceMode, youtubeUrl, error, format, language, style, music, progress, processing, inputRef, onFile, onDrop, onClear, onSourceMode, onYoutubeChange, onFormat, onLanguage, onStyle, onMusic, onStart, onCancel }: {
  file: File | null
  fileName: string
  sourceMode: 'fichier' | 'youtube'
  youtubeUrl: string
  error: string
  format: string
  language: string
  style: string
  music: boolean
  progress: number
  processing: boolean
  inputRef: React.RefObject<HTMLInputElement | null>
  onFile: (file?: File) => void
  onDrop: (event: React.DragEvent<HTMLDivElement>) => void
  onClear: () => void
  onSourceMode: (mode: 'fichier' | 'youtube') => void
  onYoutubeChange: (url: string) => void
  onFormat: (format: string) => void
  onLanguage: (language: string) => void
  onStyle: (style: string) => void
  onMusic: (enabled: boolean) => void
  onStart: () => void
  onCancel: () => void
}) {
  const activeStep = processing ? Math.min(3, Math.floor(progress / 25)) : file ? 1 : 0
  const currentAction = progress < 25 ? 'ANALYSE DE LA VIDÉO' : progress < 50 ? 'COUPES INTELLIGENTES' : progress < 75 ? 'SOUS-TITRES AUTOMATIQUES' : 'RECADRAGE & EXPORT'
  return (
    <div className="app-page new-project-page">
      <div className="page-title-row new-title-row"><div><span className="section-number">CRÉATION / NOUVEAU PROJET</span><h1>NOUVEAU MONTAGE</h1><p>Importez votre vidéo. L'IA s'occupe du reste.</p></div><button className="online-indicator button-status" onClick={() => onCancel()}><i /> MOTEUR EN LIGNE</button></div>
      <div className="new-project-grid">
        <section className="work-card import-card">
          <div className="work-card-title"><div><span className="step-label">ÉTAPE 01 / IMPORT</span><h2>Déposez votre vidéo</h2><p>MP4, MOV, WebM, MKV · jusqu'à 500 Mo</p></div><span className="step-counter">1 <i>/</i> 2</span></div>
          <div className="source-tabs"><button className={sourceMode === 'fichier' ? 'active' : ''} onClick={() => onSourceMode('fichier')}><Upload size={13} />FICHIER</button><button className={sourceMode === 'youtube' ? 'active' : ''} onClick={() => onSourceMode('youtube')}><MonitorPlay size={14} />URL YOUTUBE</button></div>
          {sourceMode === 'fichier' ? (
            <>
              <input ref={inputRef} className="hidden-input" type="file" accept=".mp4,.mov,.webm,.mkv,video/mp4,video/quicktime,video/webm,video/x-matroska" onChange={(event) => { onFile(event.currentTarget.files?.[0]); event.currentTarget.value = '' }} />
              {!file ? <div className="upload-drop" onDragOver={(event) => { event.preventDefault(); event.currentTarget.classList.add('drag-active') }} onDragLeave={(event) => event.currentTarget.classList.remove('drag-active')} onDrop={onDrop}>
                <span className="upload-symbol"><CloudUpload size={22} /></span><h3>DÉPOSEZ VOTRE VIDÉO ICI</h3><p>Glissez-déposez votre fichier ou choisissez-le depuis votre appareil.</p><button className="green-button" onClick={() => inputRef.current?.click()}><Upload size={13} /> CHOISIR UN FICHIER</button><small>MP4, MOV · 500 MO MAX</small>
              </div> : <div className="file-selected"><span className="file-selected-icon"><FileVideo2 size={22} /></span><div><strong>{fileName}</strong><small>{(file.size / (1024 * 1024)).toFixed(1)} Mo · prêt à analyser</small></div><button onClick={onClear} aria-label="Retirer le fichier"><X size={15} /></button></div>}
            </>
          ) : <div className="youtube-source"><span className="upload-symbol"><MonitorPlay size={22} /></span><h3>COLLEZ LE LIEN DE VOTRE VIDÉO</h3><input value={youtubeUrl} onChange={(event) => onYoutubeChange(event.target.value)} placeholder="https://youtube.com/watch?v=..." /><small>Vous devez détenir les droits sur le contenu. Import simulé dans le prototype.</small></div>}
          {error && <div className="upload-error" role="alert"><CircleAlert size={14} />{error}</div>}
          <div className="project-settings"><span className="step-label">RÉGLAGES DU MONTAGE</span><div className="setting-row"><div><strong>FORMAT DE SORTIE</strong><small>Choisissez votre plateforme</small></div><div className="format-buttons">{formats.map((item) => <button className={format === item ? 'active' : ''} key={item} onClick={() => onFormat(item)}>{item}</button>)}</div></div><div className="setting-row"><div><strong>LANGUE DES SOUS-TITRES</strong><small>Détection automatique disponible</small></div><label className="dark-select"><select value={language} onChange={(event) => onLanguage(event.target.value)}><option>Automatique</option><option>Français</option><option>Anglais</option></select><ChevronDown size={12} /></label></div><div className="setting-row"><div><strong>STYLE DES SOUS-TITRES</strong><small>Mot actif mis en évidence</small></div><label className="dark-select"><select value={style} onChange={(event) => onStyle(event.target.value)}><option>Karaoké</option><option>Épuré</option><option>Punchline</option><option>Menthe</option><option>Pêche</option></select><ChevronDown size={12} /></label></div><div className="setting-row"><div><strong>MUSIQUE DE FOND</strong><small>Volume abaissé sous la voix</small></div><button className={`dark-switch${music ? ' on' : ''}`} role="switch" aria-checked={music} onClick={() => onMusic(!music)}><i /></button></div></div>
          <div className="import-footer"><span><ShieldCheck size={12} />Fichier privé · suppression automatique sous 30 jours</span><button className="green-button" onClick={onStart} disabled={processing}>{processing ? 'ANALYSE EN COURS…' : 'LANCER LE MONTAGE'} <ArrowRight size={13} /></button></div>
        </section>

        <div className="analysis-column">
          <section className="work-card analysis-card">
            <div className="work-card-title"><div><span className="step-label">ÉTAPE 02 / TRAITEMENT IA</span><h2>Analyse de la vidéo</h2><p>Détection des scènes · coupes · sous-titres · recadrage</p></div><span className="step-counter">{processing ? 'EN COURS' : file ? 'PRÊT' : 'EN ATTENTE'}</span></div>
            <div className="analysis-progress-head"><span>{processing ? currentAction : file ? 'PRÊT À LANCER' : 'EN ATTENTE DU FICHIER'}</span><strong>{processing ? `${Math.round(progress)}%` : file ? '0%' : '—'}</strong></div>
            <div className="analysis-progress"><span style={{ width: `${processing ? progress : 0}%` }} /></div>
            <div className="process-checklist">{processSteps.map((step, index) => <div className={`process-check${(processing && index < activeStep) || (!processing && file && index === 0) ? ' complete' : (processing && index === activeStep) ? ' current' : ''}`} key={step}><span>{(processing && index < activeStep) || (!processing && file && index === 0) ? <Check size={11} /> : `0${index + 1}`}</span><strong>{step}</strong><small>{index === 0 ? 'DÉTECTION AUDIO' : index === 1 ? 'CONSERVATION DES RESPIRATIONS' : index === 2 ? 'FRANÇAIS / ANGLAIS' : '9:16 · 1:1 · 16:9'}</small></div>)}</div>
          </section>
          <section className="work-card preview-card"><div className="preview-card-head"><span className="step-label">APERÇU DU MONTAGE</span><span>01 / 02 · TRAITÉ</span></div><div className="empty-preview"><span className="preview-play-button"><Play size={16} fill="currentColor" /></span><span>{file ? 'L’aperçu apparaîtra automatiquement.' : 'Votre aperçu apparaîtra ici.'}</span></div><div className="preview-card-foot"><span><Scissors size={12} /> SILENCES SUPPRIMÉS</span><span>{format} · 1080p MAX</span></div></section>
          <div className="demo-disclaimer"><CircleAlert size={13} />Démo locale : la barre de progression est simulée, aucune vidéo n'est envoyée ni rendue.</div>
        </div>
      </div>
    </div>
  )
}

function ResultPage({ fileName, format, onNew, onToast }: { fileName: string; format: string; onNew: () => void; onToast: (message: string) => void }) {
  return (
    <div className="app-page result-page">
      <div className="result-heading"><div><span className="section-number">MONTAGE / EXPORT</span><h1>MONTAGE TERMINÉ.</h1><p>Votre vidéo est prête à être publiée. Vérifiez le rendu avant de l'exporter.</p></div><span className="result-success"><CheckCircle2 size={13} />SUCCÈS</span></div>
      <div className="result-grid"><section className="work-card result-preview-card"><div className="preview-card-head"><span className="step-label">APERÇU VIDÉO</span><span>1080P · {format}</span></div><button className="result-video" onClick={() => onToast('Aperçu conceptuel — le lecteur sera relié au rendu après connexion de l’API.')}><span><Play size={21} fill="currentColor" /></span><strong>{fileName}</strong><small>APERÇU DE DÉMONSTRATION</small></button><div className="result-preview-foot"><span>Durée originale <strong>08:41</strong></span><ArrowRight size={13} /><span>Après montage <strong>02:14</strong></span></div></section>
        <aside className="work-card export-card"><span className="step-label">EXPORT</span><h2>Votre vidéo est prête à être publiée.</h2><p>Choisissez un format, puis téléchargez votre fichier.</p><button className="green-button export-main" onClick={() => onToast('Le MP4 sera téléchargeable après raccordement du worker FFmpeg.')}><Download size={14} />TÉLÉCHARGER LA VIDÉO</button><button className="export-option" onClick={() => onToast('Export SRT disponible après connexion de la transcription.')}><span>.SRT · SOUS-TITRES</span><Download size={13} /></button><button className="export-option" onClick={() => onToast('Export ASS disponible après connexion de la transcription.')}><span>.ASS · STYLE KARAOKÉ</span><Download size={13} /></button><div className="export-format-note"><strong>FORMATS DISPONIBLES</strong><span>MP4 · H.264 · AAC · {format}</span><small>Les exports du prototype sont des aperçus d'interface.</small></div><button className="text-action" onClick={onNew}><Plus size={13} />NOUVEAU MONTAGE</button></aside></div>
      <div className="result-note"><ShieldCheck size={14} />Aperçu de démonstration : aucun fichier final n'a été généré.</div>
    </div>
  )
}

function ProfilePage({ onToast, onNew }: { onToast: (message: string) => void; onNew: () => void }) {
  return (
    <div className="app-page profile-page"><div className="page-title-row"><div><span className="section-number">ESPACE PERSONNEL</span><h1>MON PROFIL.</h1><p>Gérez vos informations et votre abonnement.</p></div><div className="profile-actions"><button className="outline-button" onClick={onNew}>NOUVEAU MONTAGE <ArrowRight size={12} /></button><button className="light-button" onClick={() => onToast('La modification du profil sera disponible après activation des comptes.')}>MODIFIER LE PROFIL <ArrowUpRight size={12} /></button></div></div>
      <div className="profile-grid"><section className="work-card profile-info-card"><div className="profile-card-head"><span className="step-label">INFORMATIONS PERSONNELLES</span><span className="profile-active-tag">PROFIL ACTIF</span></div><div className="profile-data"><span className="profile-avatar">AK</span><div><small>NOM</small><strong>Awa Koné</strong></div></div><div className="profile-data"><span className="profile-data-icon"><Mail size={14} /></span><div><small>EMAIL</small><strong>awa.kone@email.com</strong></div></div><button className="outline-button profile-edit" onClick={() => onToast('Édition du profil non activée dans la démo.')}>MODIFIER</button></section>
        <section className="work-card subscription-card"><div className="profile-card-head"><span className="step-label">ABONNEMENT</span><span className="profile-plan-tag">PLAN ACTIF</span></div><div className="current-plan"><span>PLAN GRATUIT</span><strong>MontageAuto Découverte</strong><p>2 vidéos / mois · jusqu'à 5 min<br />Export avec filigrane</p><div className="credit-remaining"><i /><span>2 CRÉDITS DISPONIBLES</span></div></div><span className="next-plan-label">PROCHAIN NIVEAU</span><div className="next-plan"><strong>PLAN PRO</strong><p>Vidéos de 30 min · sans filigrane</p><button className="green-button" onClick={() => onToast('Stripe sera activé avant la mise en production.')}>PASSER AU PLAN PRO <ArrowRight size={12} /></button></div></section></div>
      <div className="demo-disclaimer"><LockKeyhole size={13} />Prototype : authentification, modification de profil et paiement Stripe ne sont pas connectés.</div>
    </div>
  )
}

export default App
