// Lance AutoCut en local : backend (API + moteur de montage) et site, dans le même terminal.
// Le navigateur s'ouvre quand les deux répondent. Ctrl + C arrête tout proprement.
import { spawn, spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const backendDir = join(root, 'backend')
const isWindows = process.platform === 'win32'
const python = join(backendDir, '.venv', isWindows ? 'Scripts/python.exe' : 'bin/python')
const SITE_URL = 'http://localhost:5173'

const colors = { API: '\x1b[32m', SITE: '\x1b[36m', AUTOCUT: '\x1b[33m' }
const say = (name, line) => console.log(`${colors[name]}[${name}]\x1b[0m ${line}`)

if (!existsSync(python)) {
  say('AUTOCUT', `Environnement Python introuvable (${python}).`)
  say('AUTOCUT', 'Installez-le : cd backend && python -m venv .venv && .venv\\Scripts\\pip install -r requirements.txt')
  process.exit(1)
}

const children = []
let stopping = false

function run(name, command, args, cwd) {
  const child = spawn(command, args, { cwd, env: { ...process.env, PYTHONUNBUFFERED: '1' } })
  children.push(child)
  for (const stream of [child.stdout, child.stderr]) {
    let pending = ''
    stream.setEncoding('utf8')
    stream.on('data', (chunk) => {
      pending += chunk
      const lines = pending.split(/\r?\n/)
      pending = lines.pop() ?? ''
      for (const line of lines) if (line.trim()) say(name, line)
    })
  }
  child.on('exit', (code) => {
    if (stopping) return
    say('AUTOCUT', `${name === 'API' ? 'Le backend' : 'Le site'} s’est arrêté (code ${code}). Arrêt de l’application.`)
    stop(1)
  })
  return child
}

function killTree(child) {
  if (child.exitCode !== null || child.pid === undefined) return
  if (isWindows) {
    // /T : arrête aussi les sous-processus (worker, transcription) — aucun orphelin.
    spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
  } else {
    child.kill('SIGTERM')
  }
}

function stop(code = 0) {
  if (stopping) return
  stopping = true
  children.forEach(killTree)
  process.exit(code)
}

process.on('SIGINT', () => {
  say('AUTOCUT', 'Arrêt demandé…')
  stop(0)
})
process.on('SIGTERM', () => stop(0))

async function responds(url) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(3000) })
    return response.ok
  } catch {
    return false
  }
}

function openBrowser(url) {
  if (isWindows) spawn('cmd', ['/c', 'start', '', url], { stdio: 'ignore', detached: true })
  else spawn(process.platform === 'darwin' ? 'open' : 'xdg-open', [url], { stdio: 'ignore', detached: true })
}

run('API', python, ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000'], backendDir)
run('SITE', process.execPath, [join(root, 'node_modules', 'vite', 'bin', 'vite.js'), '--host', '::', '--strictPort'], root)

const started = Date.now()
while (!stopping) {
  const [api, site] = await Promise.all([
    responds('http://127.0.0.1:8000/api/health'),
    responds('http://127.0.0.1:5173/'),
  ])
  if (api && site) {
    say('AUTOCUT', `Application prête : ${SITE_URL}  (Ctrl + C pour tout arrêter)`)
    openBrowser(SITE_URL)
    break
  }
  if (Date.now() - started > 120000) {
    say('AUTOCUT', `Toujours en attente du ${api ? 'site' : 'backend'} après 2 min : vérifiez les messages ci-dessus.`)
    break
  }
  await new Promise((resolve) => setTimeout(resolve, 1000))
}
