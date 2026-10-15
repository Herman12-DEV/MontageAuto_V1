// Met l'API AutoCut en ligne, gratuitement, en une commande : « npm run en-ligne ».
//
//  1. démarre le backend FastAPI en local (port 8000) s'il ne tourne pas déjà ;
//  2. ouvre un tunnel Cloudflare gratuit (aucun compte, aucune carte bancaire) qui donne
//     une adresse https://….trycloudflare.com joignable depuis Internet ;
//  3. affiche l'adresse à coller dans Netlify (API_PROXY_URL).
//
// Le tunnel se ferme avec Ctrl + C — et l'adresse change à chaque redémarrage.
import { spawn, spawnSync } from 'node:child_process'
import { chmodSync, createWriteStream, existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const backendDir = join(root, 'backend')
const isWindows = process.platform === 'win32'
const python = join(backendDir, '.venv', isWindows ? 'Scripts/python.exe' : 'bin/python')
const PORT = Number(process.env.PORT ?? 8000)
const API = `http://127.0.0.1:${PORT}`

const say = (message) => console.log(`\x1b[33m[EN LIGNE]\x1b[0m ${message}`)
const children = []
let stopping = false

function stop(code = 0) {
  if (stopping) return
  stopping = true
  for (const child of children) {
    if (child.exitCode !== null || child.pid === undefined) continue
    if (isWindows) spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
    else child.kill('SIGTERM')
  }
  process.exit(code)
}

process.on('SIGINT', () => stop(0))
process.on('SIGTERM', () => stop(0))

async function responds(url) {
  try {
    return (await fetch(url, { signal: AbortSignal.timeout(3000) })).ok
  } catch {
    return false
  }
}

function run(command, args, options = {}) {
  const child = spawn(command, args, { cwd: options.cwd ?? root, env: { ...process.env, PYTHONUNBUFFERED: '1' } })
  children.push(child)
  for (const stream of [child.stdout, child.stderr]) {
    if (!stream) continue
    stream.setEncoding('utf8')
    stream.on('data', (chunk) => {
      for (const line of chunk.split(/\r?\n/)) {
        if (line.trim()) options.onLine?.(line)
      }
    })
  }
  child.on('error', (error) => {
    say(`Impossible de lancer ${command} : ${error.message}`)
    stop(1)
  })
  if (options.onExit !== false) {
    child.on('exit', (code) => {
      if (stopping) return
      say(`« ${command} » s'est arrêté (code ${code}). Arrêt.`)
      stop(1)
    })
  }
  return child
}

async function download(url, destination) {
  const response = await fetch(url, { redirect: 'follow' })
  if (!response.ok || !response.body) throw new Error(`téléchargement refusé (${response.status})`)
  await pipeline(Readable.fromWeb(response.body), createWriteStream(destination))
}

function cloudflaredAsset() {
  const { platform, arch } = process
  if (platform === 'win32') return 'cloudflared-windows-amd64.exe'
  if (platform === 'linux') return arch === 'arm64' ? 'cloudflared-linux-arm64' : 'cloudflared-linux-amd64'
  return null // macOS : « brew install cloudflared » (une compilation, pas un simple fichier)
}

async function findCloudflared() {
  const lookup = spawnSync(isWindows ? 'where' : 'which', ['cloudflared'], { encoding: 'utf8' })
  if (lookup.status === 0 && lookup.stdout.trim()) return lookup.stdout.trim().split(/\r?\n/)[0]

  const binary = join(root, '.cloudflared', isWindows ? 'cloudflared.exe' : 'cloudflared')
  if (existsSync(binary)) return binary

  const asset = cloudflaredAsset()
  if (!asset) return null

  say('Première utilisation : téléchargement de cloudflared (~30 Mo, une seule fois)…')
  mkdirSync(dirname(binary), { recursive: true })
  await download(`https://github.com/cloudflare/cloudflared/releases/latest/download/${asset}`, binary)
  if (!isWindows) chmodSync(binary, 0o755)
  return binary
}

if (!existsSync(python)) {
  say('Environnement Python introuvable : ' + python)
  say('Installez-le une fois avec :')
  say('  cd backend && python -m venv .venv && .venv\\Scripts\\pip install -r requirements.txt   (Windows)')
  say('  cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt      (Linux/macOS)')
  process.exit(1)
}

// 1. Backend : on le démarre seulement s'il ne répond pas déjà.
if (await responds(`${API}/api/health`)) {
  say(`Le backend tourne déjà sur ${API} — on le réutilise.`)
} else {
  say(`Démarrage du backend sur ${API}…`)
  run(python, ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', String(PORT)], {
    cwd: backendDir,
    onLine: (line) => say(`[API] ${line}`),
  })
  const started = Date.now()
  while (!(await responds(`${API}/api/health`)) && Date.now() - started < 90000) {
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
  if (!(await responds(`${API}/api/health`))) {
    say("Le backend n'a pas répondu en 90 secondes : regardez les messages ci-dessus.")
    stop(1)
  }
  say('Backend prêt.')
}

// 2. Tunnel Cloudflare : adresse publique gratuite, sans compte.
let cloudflared
try {
  cloudflared = await findCloudflared()
} catch (error) {
  say(`Téléchargement impossible : ${error.message}`)
}
if (!cloudflared) {
  say('cloudflared est introuvable.')
  say('macOS : « brew install cloudflared » puis relancez « npm run en-ligne ».')
  say('Autre système : https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/')
  stop(1)
}

say('Ouverture du tunnel…')
let publicUrl = null
let onTunnelLine = () => {}
const tunnel = run(cloudflared, ['tunnel', '--url', API, '--no-autoupdate'], {
  onLine: (line) => {
    if (!publicUrl) {
      const match = line.match(/https:\/\/[a-z0-9-]+\.trycloudflare\.com/i)
      if (match) publicUrl = match[0]
    }
    onTunnelLine(line)
  },
})

const started = Date.now()
while (!publicUrl && Date.now() - started < 60000) {
  await new Promise((resolve) => setTimeout(resolve, 500))
}

if (!publicUrl) {
  say("Le tunnel n'a pas fourni d'adresse. Dernières lignes de cloudflared :")
  stop(1)
}

console.log(`
\x1b[32m═══════════════════════════════════════════════════════════════════════\x1b[0m
  \x1b[1mL'API AutoCut est en ligne :\x1b[0m  \x1b[36m${publicUrl}\x1b[0m

  1) Testez dans le navigateur :  ${publicUrl}/api/health
  2) Netlify → Site configuration → Environment variables :
        API_PROXY_URL = ${publicUrl}
  3) Netlify → Deploys → Trigger deploy → « Clear cache and deploy site »
  4) Firebase → Authentication → Settings → Authorized domains :
        ajoutez l'adresse de votre site Netlify (ex. autocut.netlify.app)

  \x1b[33mLaissez cette fenêtre ouverte.\x1b[0m Ctrl + C pour tout arrêter.
  L'adresse change à chaque redémarrage : reprenez à l'étape 2 si besoin.
\x1b[32m═══════════════════════════════════════════════════════════════════════\x1b[0m
`)

onTunnelLine = (line) => {
  if (/error|failed|ERR/i.test(line)) say(`[TUNNEL] ${line}`)
}
