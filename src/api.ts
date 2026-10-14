// Client de l’API AutoCut : session Firebase, appels JSON, envoi des vidéos dans Firebase Storage.
import { useEffect, useState } from 'react'
import { onAuthStateChanged, signOut } from 'firebase/auth'
import type { User as FirebaseUser } from 'firebase/auth'
import { deleteObject, getDownloadURL, listAll, ref, uploadBytesResumable } from 'firebase/storage'
import { auth, storage } from './lib/firebase'

export type Quota = {
  plan: 'free' | 'pro' | 'agence'
  plan_label: string
  used: number
  limit: number | null
  remaining: number | null
  unlimited: boolean
  max_duration_s: number
  watermark: boolean
  period: string
}

export type Prefs = {
  language: 'auto' | 'fr' | 'en'
  subtitle_style: string
  format: '9:16' | '1:1' | 'original'
  notify_email: boolean
  auto_analyse: boolean
}

export type User = {
  id: string
  username: string | null
  email: string | null
  name: string
  has_password: boolean
  google_linked: boolean
  plan: Quota['plan']
  plan_renews_at: string | null
  has_subscription: boolean
  prefs: Prefs
  quota: Quota
  created_at: string
}

export type ProjectStatus = 'queued' | 'processing' | 'done' | 'failed'
export type Stage = 'attente' | 'analyse' | 'transcription' | 'montage' | 'encodage' | 'termine'

export type ProjectOptions = {
  silence_db: number
  min_silence: number
  padding_ms: number
  language: Prefs['language']
  subtitles: boolean
  subtitle_style: string
  format: Prefs['format']
  music: string | null
  music_volume: number
  cut_silences: boolean
  mode: 'full' | 'shorts'
  shorts_count: number
  shorts_duration: number
}

export type Short = {
  index: number
  title: string
  duration: number
  video: string
  video_download: string
  srt: string | null
}

export type Project = {
  id: string
  title: string
  status: ProjectStatus
  job_kind: 'full' | 'rerender'
  stage: Stage
  progress: number
  error: string | null
  source_kind: 'upload' | 'youtube'
  source_filename: string
  storage_path: string | null
  options: ProjectOptions
  duration_in: number | null
  duration_out: number | null
  cuts: number | null
  saved_pct: number | null
  language: string | null
  width: number | null
  height: number | null
  fps: number | null
  created_at: string
  finished_at: string | null
  expires_at: string
  mode: 'full' | 'shorts'
  media?: {
    video?: string
    video_download?: string
    srt?: string
    ass?: string
    txt?: string
    shorts?: Short[]
  }
  has_transcript?: boolean
  queue_position?: number | null
}

export type SubtitleStyle = { key: string; label: string; description: string }
export type MusicTrack = { id: string; title: string; mood: string; bpm: number; license: string; author: string }
export type Library = {
  styles: SubtitleStyle[]
  music: MusicTrack[]
  formats: { key: Prefs['format']; label: string; hint: string }[]
  languages: { key: Prefs['language']; label: string }[]
  limits: { max_upload_bytes: number; retention_days: number }
}

export type Phrase = { index: number; start: number | null; end: number | null; text: string }

export class ApiError extends Error {
  status: number
  code: string
  data: Record<string, unknown>

  constructor(status: number, code: string, message: string, data: Record<string, unknown> = {}) {
    super(message)
    this.status = status
    this.code = code
    this.data = data
  }
}

// --- Session (Firebase Auth) ------------------------------------------------------
// L'identité est gérée par Firebase Auth ; le backend vérifie le jeton d'identité Firebase
// envoyé à chaque requête et associe un compte AutoCut (quota, offre, montages).

const SESSION_EVENT = 'autocut:session'

let currentUser: User | null = null
let firebaseUser: FirebaseUser | null = auth.currentUser
let authReady = false

function emitSession() {
  window.dispatchEvent(new CustomEvent(SESSION_EVENT))
}

onAuthStateChanged(auth, (next) => {
  firebaseUser = next
  authReady = true
  if (!next) currentUser = null
  emitSession()
  if (next) refreshUser().catch(() => undefined)
})

/** Jeton d'identité Firebase, renouvelé automatiquement par le SDK (validité 1 h). */
export async function getToken(): Promise<string | null> {
  return firebaseUser ? firebaseUser.getIdToken() : null
}

export function setUser(user: User) {
  currentUser = user
  emitSession()
}

export async function clearSession() {
  currentUser = null
  await signOut(auth)
}

export function isLoggedIn(): boolean {
  return firebaseUser !== null
}

/** État de connexion : « ready » passe à vrai quand Firebase a restauré la session. */
export function useAuthState(): { ready: boolean; loggedIn: boolean } {
  const [state, setState] = useState({ ready: authReady, loggedIn: firebaseUser !== null })
  useEffect(() => {
    const sync = () => setState({ ready: authReady, loggedIn: firebaseUser !== null })
    window.addEventListener(SESSION_EVENT, sync)
    sync()
    return () => window.removeEventListener(SESSION_EVENT, sync)
  }, [])
  return state
}

/** Utilisateur connecté, rechargé depuis l’API au premier usage et après chaque changement. */
export function useUser(): User | null {
  const [user, setLocal] = useState<User | null>(currentUser)

  useEffect(() => {
    const sync = () => setLocal(currentUser)
    window.addEventListener(SESSION_EVENT, sync)
    if (!currentUser && firebaseUser) refreshUser().catch(() => undefined)
    return () => window.removeEventListener(SESSION_EVENT, sync)
  }, [])

  return user
}

export async function refreshUser(): Promise<User> {
  const user = await api<User>('/api/me')
  setUser(user)
  return user
}

// --- Appels -------------------------------------------------------------------

type Options = { method?: string; body?: unknown; signal?: AbortSignal }

// Le serveur peut être absent quelques secondes (démarrage, redémarrage automatique après
// une modification du code) : on réessaie pendant ~30 s avant d'afficher une erreur.
const RETRY_DELAYS_MS = [500, 1000, 1500, 2000, 3000, 4000, 5000, 6000, 7000]

function wait(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => {
      window.clearTimeout(timer)
      reject(new DOMException('Annulé', 'AbortError'))
    })
  })
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const headers: Record<string, string> = {}
  const token = await getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'

  for (let attempt = 0; ; attempt += 1) {
    let response: Response | null = null
    try {
      response = await fetch(path, {
        method: options.method ?? (options.body !== undefined ? 'POST' : 'GET'),
        headers,
        body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
        signal: options.signal,
      })
    } catch (error) {
      if ((error as Error).name === 'AbortError') throw error
    }
    // Requête qui n'a jamais atteint l'API (site ou backend indisponible) : nouvel essai sans risque.
    const unreachable = response === null || response.status === 502 || response.status === 504 ||
      (response.status === 503 && response.headers.get('content-type')?.includes('json') &&
        (await response.clone().text()).includes('backend_down'))
    if (!unreachable) return parse<T>(response as Response)
    if (attempt >= RETRY_DELAYS_MS.length) {
      if (response) return parse<T>(response)
      throw new ApiError(
        0,
        'network',
        'Le site ne parvient pas à joindre le serveur AutoCut. Vérifiez que « npm start » tourne toujours, puis réessayez.',
      )
    }
    await wait(RETRY_DELAYS_MS[attempt], options.signal)
  }
}

async function parse<T>(response: Response): Promise<T> {
  const text = await response.text()
  let data: unknown = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }
  if (!response.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail
    if (response.status === 401 && firebaseUser) {
      clearSession().catch(() => undefined)
      if (window.location.hash.startsWith('#/app')) window.location.hash = '#/connexion'
    }
    if (detail && typeof detail === 'object' && 'message' in detail) {
      const { code, message, ...rest } = detail as { code: string; message: string }
      throw new ApiError(response.status, code, message, rest)
    }
    throw new ApiError(response.status, 'error', 'Une erreur est survenue. Réessayez.')
  }
  return data as T
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Une erreur est survenue. Réessayez.'
}

// --- Envoi des vidéos dans Firebase Storage ----------------------------------------

export type StoredVideo = { path: string; url: string; filename: string; size: number }

function safeName(name: string) {
  return name.normalize('NFKD').replace(/[^\w.-]+/g, '-').replace(/-+/g, '-').slice(-120)
}

/**
 * Envoie la vidéo dans le dossier de l’utilisateur (« users/{uid}/sources/… »).
 * L’envoi est découpé et repris automatiquement par le SDK en cas de coupure réseau.
 */
export function uploadFile(
  file: File,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<StoredVideo> {
  const uid = firebaseUser?.uid
  if (!uid) return Promise.reject(new ApiError(401, 'unauthorized', 'Connectez-vous pour importer une vidéo.'))
  const path = `users/${uid}/sources/${Date.now()}-${safeName(file.name)}`
  const fileRef = ref(storage, path)
  const task = uploadBytesResumable(fileRef, file, {
    contentType: file.type || 'video/mp4',
    customMetadata: { originalName: file.name },
  })
  signal?.addEventListener('abort', () => task.cancel())
  return new Promise((resolve, reject) => {
    task.on(
      'state_changed',
      (snap) => onProgress(snap.totalBytes ? snap.bytesTransferred / snap.totalBytes : 0),
      (error) => {
        if (error.code === 'storage/canceled') reject(new DOMException('Annulé', 'AbortError'))
        else reject(new ApiError(0, error.code, storageErrorMessage(error.code)))
      },
      () => {
        getDownloadURL(fileRef)
          .then((url) => resolve({ path, url, filename: file.name, size: file.size }))
          .catch((error) => reject(new ApiError(0, error.code, storageErrorMessage(error.code))))
      },
    )
  })
}

/** Supprime un fichier du Storage de l’utilisateur (sans erreur s’il n’existe plus). */
export async function deleteStoredFile(path: string | null | undefined) {
  if (!path) return
  try {
    await deleteObject(ref(storage, path))
  } catch (error) {
    if ((error as { code?: string }).code !== 'storage/object-not-found') throw error
  }
}

/** CRUD — renommer un montage. */
export function renameProject(id: string, title: string) {
  return api<Project>(`/api/projects/${id}`, { method: 'PATCH', body: { title } })
}

/** CRUD — supprimer un montage et sa vidéo source du Storage. */
export async function deleteProject(project: Pick<Project, 'id' | 'storage_path'>) {
  await api(`/api/projects/${project.id}`, { method: 'DELETE' })
  await deleteStoredFile(project.storage_path).catch(() => undefined)
}

/** Supprime tous les fichiers de l’utilisateur dans le Storage (suppression du compte). */
export async function deleteAllStoredFiles(uid: string) {
  const walk = async (path: string): Promise<void> => {
    const listing = await listAll(ref(storage, path))
    await Promise.all(listing.items.map((item) => deleteObject(item)))
    await Promise.all(listing.prefixes.map((prefix) => walk(prefix.fullPath)))
  }
  await walk(`users/${uid}`)
}

function storageErrorMessage(code: string): string {
  switch (code) {
    case 'storage/unauthorized':
      return 'Envoi refusé par le stockage : vérifiez que vous êtes connecté (et les règles du Storage).'
    case 'storage/quota-exceeded':
      return 'Espace de stockage plein. Réessayez plus tard.'
    case 'storage/retry-limit-exceeded':
      return 'Connexion interrompue pendant l’envoi. Réessayez.'
    default:
      return 'L’envoi de la vidéo a échoué. Réessayez.'
  }
}

// --- Petits utilitaires d’affichage ----------------------------------------------

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return '--:--'
  const total = Math.round(seconds)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(s).padStart(2, '0')
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

/** 30 → « 30 s » ; 150 → « 2 min 30 » */
export function formatSeconds(seconds: number): string {
  const total = Math.round(seconds)
  if (total < 60) return `${total} s`
  const s = total % 60
  return `${Math.floor(total / 60)} min${s ? ` ${String(s).padStart(2, '0')}` : ''}`
}

export function formatDay(iso: string | null | undefined): string {
  if (!iso) return ''
  const date = new Date(iso)
  const today = new Date()
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const diff = Math.round((startOf(today) - startOf(date)) / 86400000)
  if (diff === 0) return 'Aujourd’hui'
  if (diff === 1) return 'Hier'
  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
}

let libraryCache: Promise<Library> | null = null

export function getLibrary(): Promise<Library> {
  if (!libraryCache) {
    libraryCache = api<Library>('/api/library').catch((error) => {
      libraryCache = null
      throw error
    })
  }
  return libraryCache
}

export type Health = { status: 'ok' | 'degraded'; ffmpeg: boolean; workers: number }

/** État du moteur, rafraîchi toutes les 30 s (indicateur « Moteur IA en ligne »). */
export function useEngineOnline(): boolean | null {
  const [online, setOnline] = useState<boolean | null>(null)
  useEffect(() => {
    let alive = true
    const check = () =>
      api<Health>('/api/health')
        .then((h) => alive && setOnline(h.status === 'ok'))
        .catch(() => alive && setOnline(false))
    check()
    const timer = window.setInterval(check, 30000)
    return () => {
      alive = false
      window.clearInterval(timer)
    }
  }, [])
  return online
}
