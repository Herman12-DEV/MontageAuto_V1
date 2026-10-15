# Mettre AutoCut en ligne — gratuit — avec CI/CD Netlify

Guide pas à pas. Objectif : **le site est publié automatiquement à chaque `git push` sur `main`**, avec
une intégration continue qui vérifie le frontend et le backend avant chaque mise en ligne.

---

## 1. Ce qui peut aller sur Netlify (gratuit) — et ce qui ne peut pas

| Élément | Où ça tourne | Pourquoi |
|---|---|---|
| Interface React (`src/`, compilée dans `dist/`) | **Netlify** (plan *Starter*, 0 €) | Fichiers statiques + HTTPS + domaine : c'est exactement le terrain de Netlify |
| API FastAPI (`backend/app`) | **Ailleurs** (VPS, tunnel Cloudflare, HF Spaces…) | Netlify n'exécute pas de Python ni de processus longs |
| Worker de montage + FFmpeg + faster-whisper | **Ailleurs** | Plusieurs minutes de CPU par vidéo, plusieurs centaines de Mo de RAM : impossible en hébergement statique |
| Base SQLite / PostgreSQL, vidéos de sortie (`backend/storage/projects/`) | **Ailleurs**, sur un disque persistant | Netlify n'a pas de disque |
| Authentification + vidéos importées | **Firebase** (déjà configuré dans le dépôt) | `autocut-eb855` : Auth + Storage |

Autrement dit : **Netlify héberge le site, et le site appelle le backend par un proxy `/api/*`**.
Le navigateur ne voit qu'un seul domaine → aucune CORS à gérer, aucun secret dans le frontend.

```
Navigateur
   │  https://autocut.netlify.app
   ▼
Netlify (dist/ statique)  ──/api/*──►  Backend FastAPI (VPS / tunnel / HF Space)
   │                                        │  FFmpeg + Whisper (worker)
   │  Firebase Auth / Storage (jetons)      ▼
   └──────────────────────────────────►  Firebase  autocut-eb855
```

Le fichier `netlify.toml` (déjà dans le dépôt) contient toute la configuration de build, et
`scripts/netlify-postbuild.mjs` écrit `dist/_redirects`, qui contient le proxy `/api/*` puis le repli SPA.

---

## 2. Mettre le dépôt sous intégration continue (GitHub Actions)

Rien à faire : `.github/workflows/ci.yml` s'exécute à chaque poussée et à chaque pull request.

- `Site — typecheck et compilation` : `npm ci`, `npm run typecheck`, `npm run build`, site conservé en artefact.
- `API et moteur — pytest` : installe FFmpeg (avec libass) + Python 3.11, puis lance toute la suite
  (66 cas : moteur FFmpeg réel, API, worker, Firebase, paiement) avec la couverture.

Pour l'afficher en haut du README :

```markdown
![CI](https://github.com/Herman12-DEV/MontageAuto_V1/actions/workflows/ci.yml/badge.svg)
```

> À la fin de la première exécution, si l'onglet **Actions** du dépôt affiche un bandeau demandant
> d'autoriser les workflows : cliquez sur **I authorize workflows**. Nécessaire une seule fois après
> l'ajout d'un premier fichier de workflow.

---

## 3. Publier le site sur Netlify (10 minutes, une seule fois)

1. **Compte** — https://app.netlify.com → *Sign up* → **GitHub** (connexion avec le compte qui possède le dépôt).
2. **Nouveau site** — *Add new site* → **Import an existing project** → **GitHub** → autoriser Netlify
   à lire `Herman12-DEV/MontageAuto_V1` → choisir **MontageAuto_V1**.
3. **Réglages de compilation** — Netlify les lit dans `netlify.toml`, donc tout est déjà bon :
   - Branch to deploy : `main`
   - Build command : `npm run build`
   - Publish directory : `dist`
   - Node : 22.14.0 (via `.nvmrc`)
   Cliquez sur **Deploy**.
4. **Variable d'environnement** — *Site configuration* → **Environment variables** → *Add a variable* :

   | Clé | Valeur | Portée |
   |---|---|---|
   | `API_PROXY_URL` | `https://api.votre-domaine.com` (adresse **publique** du backend, voir §4) | All deploys |

   Puis *Deploys* → **Trigger deploy** → *Clear cache and deploy site* pour reconstruire `dist/_redirects`.
   Sans cette variable, le site se déploie quand même, mais les appels `/api/*` répondent 404 :
   l'interface affiche « Le site ne parvient pas à joindre le serveur AutoCut ».
5. **Domaine** — un sous-domaine gratuit `…netlify.app` est fourni. *Domain management* → *Add a domain*
   pour un domaine personnel (HTTPS automatique, gratuit).
6. **Autoriser le nouveau domaine côté Firebase** (sinon la connexion échoue avec
   `auth/unauthorized-domain`) :
   - https://console.firebase.google.com → projet `autocut-eb855` → **Authentication** → onglet
     **Settings** → **Authorized domains** → *Add domain* → `ton-site.netlify.app` (+ ton domaine perso).
   - Si « Continuer avec Google » doit fonctionner : https://console.cloud.google.com →
     *API et services* → *Identifiants* → ton **ID client OAuth (Application Web)** →
     *Origines JavaScript autorisées* → ajouter `https://ton-site.netlify.app`.
7. **Côté backend**, mets `PUBLIC_URL=https://ton-site.netlify.app` dans `backend/.env` puis redémarre :
   les liens des e-mails (« votre montage est prêt ») et les retours Stripe pointeront vers Netlify.

C'est terminé : **chaque `git push` sur `main` redéploie le site automatiquement** (intégration Git
native de Netlify, sans aucun secret à gérer).

---

## 4. Rendre le backend joignable (l'autre moitié)

Choisis une option. Les quatre donnent une URL **https** utilisable comme `API_PROXY_URL`.

### A. Tunnel Cloudflare depuis une machine à toi — 0 €, sans carte bancaire

Idéal pour démarrer : la machine (PC, serveur maison) garde le disque, la base et FFmpeg.

```bash
# Sur la machine qui exécute le backend (port 8000)
npm ci && npm run build                     # une fois
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                        # APP_ENV=development suffit ici
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000   # + worker intégré (EMBEDDED_WORKER=true)

# Dans un autre terminal : tunnel éphémère (URL aléatoire, change à chaque redémarrage)
cloudflared tunnel --url http://localhost:8000
# → https://xxxx-yyyy-zzzz.trycloudflare.com   ← à mettre dans API_PROXY_URL
```

Pour une URL **stable**, crée un compte Cloudflare (gratuit, sans carte), un domaine (≈ 8 €/an), puis :

```bash
cloudflared tunnel login
cloudflared tunnel create autocut
cloudflared tunnel route dns autocut api.votre-domaine.com
cloudflared tunnel run --url http://localhost:8000 autocut   # ou en service systemd
```

> La machine doit rester allumée. Fermée = site en ligne mais API injoignable (messages d'erreur explicites côté interface).

### B. VPS payant (~5 €/mois) — le plus solide

Tout est déjà décrit dans le README (§ *Mise en production*), avec `deploy/autocut-api.service`,
`deploy/autocut-worker@.service` et `deploy/Caddyfile` (HTTPS Let's Encrypt automatique sur
`api.votre-domaine.com`). C'est la seule option qui encaisse un vrai trafic de montage.

### C. Oracle Cloud *Always Free* — 0 € à vie (carte bancaire pour vérifier l'identité)

VM ARM Ampere A1 (jusqu'à 4 cœurs / 24 Go de RAM, gratuite en permanence) : largement de quoi faire
tourner FFmpeg + faster-whisper. Procédure = option B (Debian/Ubuntu 24.04 + les 3 fichiers de `deploy/`).

### D. Hugging Face Spaces (Docker) — 0 €, 16 Go de RAM, mais éphémère

Crée un *Space* Docker (2 vCPU / 16 Go gratuits) qui expose le port 7860 et démarre
`uvicorn app.main:app --host 0.0.0.0 --port 7860`. Deux limites à connaître :

- le *Space* **s'endort** après une période sans visite (la première requête le réveille en ~1 min) ;
- **le disque est effacé** à chaque redémarrage : monte une base externe gratuite (Neon/Supabase) via
  `DATABASE_URL` et accepte de perdre les fichiers de `backend/storage/projects` (les vidéos importées,
  elles, sont dans Firebase Storage et ne sont pas concernées).

Dans tous les cas, `API_PROXY_URL` doit être une URL **https** publique, et le backend n'a pas besoin
d'autoriser le domaine Netlify (les appels passent par le proxy Netlify, donc en même origine).

---

## 5. Deux façons de faire le déploiement continu

### Méthode 1 (recommandée) — intégration Git de Netlify, aucun secret

Netlify surveille `main` : *push* = *build* = *deploy*. C'est ce qui est décrit au §3.
`.github/workflows/deploy-netlify.yml` existe aussi : si les secrets de la méthode 2 ne sont pas
définis, il se termine en **succès** avec une simple note explicative (aucun voyant rouge inutile).

### Méthode 2 — le déploiement piloté par GitHub Actions

À préférer si tu veux que les tests CI bloquent la publication, ou publier depuis une autre branche.

1. **Jeton Netlify** : https://app.netlify.com → *User settings* → **Applications** →
   *Personal access tokens* → **New access token** → copier la valeur.
2. **Identifiant du site** : *Site configuration* → *General* → **Site ID**
   (ou `npx netlify-cli@27 link` puis `.netlify/state.json`).
3. Dans GitHub : *Settings* → **Secrets and variables** → **Actions** :
   - *Secrets* : `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID` (et `FIREBASE_SERVICE_ACCOUNT` si tu veux
     publier automatiquement `storage.rules`).
   - *Variables* : `API_PROXY_URL`.
4. Lancer une fois l'onglet **Actions** → *Déploiement Netlify* → **Run workflow**.

```bash
# Équivalent en local (le jeton reste dans la variable d'environnement)
NETLIFY_AUTH_TOKEN=… NETLIFY_SITE_ID=… npm run netlify:deploy
```

---

## 6. Récapitulatif des variables

| Où | Nom | Valeur | Rôle |
|---|---|---|---|
| Netlify (env var) + GitHub (variable) | `API_PROXY_URL` | `https://api.votre-domaine.com` | Cible du proxy `/api/*` (écrit dans `dist/_redirects` au build) |
| `backend/.env` | `PUBLIC_URL` | `https://ton-site.netlify.app` | Liens des e-mails et retours Stripe |
| `backend/.env` | `APP_ENV=production`, `SECRET_KEY=…`, `DATABASE_URL=…` | voir README | Le backend refuse de démarrer en production sans ces valeurs |
| `backend/.env` (facultatif) | `CORS_ORIGINS=https://ton-site.netlify.app` | — | Utile uniquement si un client appelle l'API **sans** passer par le proxy |
| GitHub (secret) | `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID` | §5 | Déploiement piloté par GitHub Actions |

---

## 7. Recette après la mise en ligne

1. `https://ton-site.netlify.app` s'ouvre, en HTTPS, sans erreur console.
2. **Créer un compte** (nom d'utilisateur + mot de passe) → connexion immédiate.
   Échec `auth/unauthorized-domain` → revoir §3.6.
3. Tableau de bord : la pastille « moteur en ligne » est verte (elle interroge `/api/health` via le proxy).
   Rouge/« serveur injoignable » → `API_PROXY_URL` est vide ou le backend est éteint.
4. Importer une petite vidéo (≤ 1 min) → le montage passe les étapes *analyse → transcription → montage*
   et se termine ; la vidéo est téléchargeable.
5. Onglets *Mes montages*, *Mon profil*, *Paramètres* et mode **Shorts** fonctionnent.
6. Sur téléphone : le recadrage 9:16 s'affiche correctement.

---

## 8. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `404` sur `/api/health`, message « serveur AutoCut ne répond pas » | `API_PROXY_URL` absente (pas de règle `/api/*` dans `dist/_redirects`) | Ajouter la variable dans Netlify puis *Clear cache and deploy* |
| `403`/`502` sur `/api/*` | URL du backend fausse, backend éteint, ou tunnel Cloudflare fermé | Ouvrir `API_PROXY_URL/api/health` dans le navigateur : doit renvoyer du JSON |
| `auth/unauthorized-domain` à la connexion | Domaine netlify absent de Firebase Auth | §3.6 |
| Le popup Google se ferme aussitôt | Origine JavaScript manquante côté Google OAuth | §3.6 (2ᵉ puce) |
| Montage bloqué en « attente » | Aucun worker actif (`EMBEDDED_WORKER=false` sans `systemctl start autocut-worker@1`) | Démarrer le worker |
| Build Netlify en échec TypeScript | Voir l'onglet *Deploys* → *Failed deploy* : la CI (`ci.yml`) reproduit l'erreur en local | `npm run typecheck` |
| Dépassement de quota Netlify | 100 Go de bande passante et 300 min de build par mois (offre gratuite) | Les vidéos ne transitent pas par Netlify (Firebase Storage → backend), seul le JSON passe |

---

## 9. Coûts et limites (offre Netlify *Starter*, gratuite)

- 100 Go de bande passante / mois, 300 minutes de build / mois, 1 build simultané, sites illimités.
- HTTPS + domaine personnalisé + déploiements de prévisualisation (utiles pour tester une branche
  avant `main`) : inclus.
- GitHub Actions : gratuit et illimité pour un dépôt public ; le workflow `ci.yml` dure ~5 minutes.
- Rappel : ce qui coûte de l'argent, c'est **le calcul vidéo** (FFmpeg + Whisper), pas le site.
  Si tu restes sur l'option A (tunnel depuis ta machine) ou C (Oracle Always Free), la facture totale
  reste à 0 €.
