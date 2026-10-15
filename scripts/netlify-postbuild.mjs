// Génère « dist/_redirects » après la compilation du site.
//
// Netlify lit ce fichier pour rediriger les appels :
//   /api/*  →  API_PROXY_URL/api/*   (le backend FastAPI, proxy transparent : aucune CORS à gérer)
//   /*      →  /index.html           (repli SPA : les adresses du type /#/app/montages)
//
// API_PROXY_URL se règle dans Netlify (Site configuration → Environment variables) ou en local :
//   API_PROXY_URL=https://api.votre-domaine.com npm run build
// Sans cette variable, seul le repli SPA est écrit et le site appellera /api sur son propre domaine.
import { writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const dist = join(root, 'dist')
const target = (process.env.API_PROXY_URL ?? '').trim().replace(/\/+$/, '')

const rules = []
if (target) rules.push(`/api/*  ${target}/api/:splat  200`)
rules.push('/*  /index.html  200')

writeFileSync(join(dist, '_redirects'), `${rules.join('\n')}\n`)

if (target) {
  console.log(`[netlify] /api/* → ${target}/api/*`)
} else if (process.env.NETLIFY === 'true') {
  console.log(
    '[netlify] API_PROXY_URL non défini : le site appellera /api sur son propre domaine. ' +
      'Renseignez API_PROXY_URL (Site configuration → Environment variables) pour relier le backend, puis relancez un déploiement.',
  )
} else {
  console.log('[netlify] API_PROXY_URL non défini : proxy /api absent de dist/_redirects.')
}
