# AutoCut (MontageAuto) — plateforme de montage vidéo automatique

[![CI](https://github.com/Herman12-DEV/MontageAuto_V1/actions/workflows/ci.yml/badge.svg)](https://github.com/Herman12-DEV/MontageAuto_V1/actions/workflows/ci.yml)
[![Déploiement Netlify](https://github.com/Herman12-DEV/MontageAuto_V1/actions/workflows/deploy-netlify.yml/badge.svg)](https://github.com/Herman12-DEV/MontageAuto_V1/actions/workflows/deploy-netlify.yml)

Déposez une vidéo brute, récupérez en quelques minutes une vidéo **sans silences**, **sous-titrée mot par mot (karaoké)**, avec **musique de fond dosée sous la voix**, **recadrée en 9:16** et prête à publier.

```
autocut/
├── src/                 Frontend React 19 + TypeScript (Vite)
├── backend/             API FastAPI, worker de montage, moteur FFmpeg + Whisper
│   ├── app/engine/      silences · transcription · sous-titres · rendu · YouTube
│   ├── app/routers/     auth · profil · uploads · montages · paiement · catalogue
│   ├── music/           20 pistes libres de droits (CC0) + registre des licences
│   ├── scripts/         génération de la bibliothèque musicale
│   └── tests/           tests unitaires, d'intégration (FFmpeg réel) et de recette
├── deploy/              services systemd + Caddy (HTTPS) pour un VPS
├── docs/                guides (mise en ligne gratuite Netlify, CI/CD)
└── .github/workflows/   intégration continue + déploiement Netlify
```

## Stack

| Couche | Technologie |
|---|---|
| Interface | React 19, TypeScript, Vite 8, CSS natif |
| API | Python 3.11+ · FastAPI · SQLAlchemy 2 |
| Base de données | SQLite (dev) · PostgreSQL (production) |
| File d'attente | Table `projects` + workers `python -m app.worker` (voir *Choix techniques*) |
| Moteur vidéo | FFmpeg (silencedetect, select/aselect, libass, sidechaincompress) |
| Transcription | faster-whisper (int8, CPU), horodatage mot à mot, filtre VAD |
| Paiement | Stripe Checkout + webhooks |
| Import YouTube | yt-dlp |

## Installation (développement)

Prérequis : **Node.js 22.12+**, **Python 3.11+**, **FFmpeg** (avec libass).

- Windows : `winget install Gyan.FFmpeg`
- Ubuntu/Debian : `sudo apt install ffmpeg fonts-dejavu fonts-liberation`
- macOS : `brew install ffmpeg`

```bash
# 1. Backend (une seule fois)
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows   (Linux/macOS : source .venv/bin/activate)
pip install -r requirements-dev.txt
cp .env.example .env            # Windows : copy .env.example .env
python -m scripts.generate_music   # ~4 min, une seule fois (déjà fait si music/ est rempli)
cd ..
npm install

# 2. Lancer l'application (backend + site, navigateur ouvert automatiquement)
npm start                       # ou double-clic sur lancer.bat — Ctrl + C arrête tout
```

En dev, un worker tourne **dans le processus de l'API** (`EMBEDDED_WORKER=true`) : rien d'autre à lancer.
Au premier montage, le modèle Whisper est téléchargé (≈ 480 Mo pour `small`) dans `backend/storage/models`.

**Comptes** : l'inscription demande seulement un nom d'utilisateur et un mot de passe, et connecte
immédiatement (aucune confirmation par e-mail). On se reconnecte avec son nom d'utilisateur (ou son
e-mail s'il en a ajouté un dans « Mon profil », ce qui permet aussi « Mot de passe oublié »), ou avec Google.

**Activer « Continuer avec Google »** (gratuit, 5 minutes) :

1. https://console.cloud.google.com → créer un projet → *API et services* → *Écran de consentement OAuth*
   (type « Externe », nom de l'application, e-mail d'assistance).
2. *Identifiants* → *Créer des identifiants* → *ID client OAuth* → type **Application Web**.
3. *Origines JavaScript autorisées* : `http://localhost:5173` (dev) et `https://votre-domaine.com` (prod).
   Google refuse les adresses IP : depuis un téléphone, le bouton ne marche qu'une fois le site en HTTPS.
4. Copier l'ID client (`….apps.googleusercontent.com`) dans `backend/.env` : `GOOGLE_CLIENT_ID=…`,
   puis relancer le backend.

### Firebase (authentification et stockage des vidéos)

L'interface se connecte avec **Firebase Auth** (projet `autocut-eb855`) et envoie les vidéos importées
dans **Firebase Storage**, dans le dossier `users/{uid}/` de chaque utilisateur. Le backend vérifie le jeton
Firebase à chaque requête (clés publiques de Google, aucune clé secrète requise) et télécharge la vidéo
pour la monter. Réglages côté serveur : `FIREBASE_PROJECT_ID` et `FIREBASE_STORAGE_BUCKET` dans `backend/.env`.

À faire **une fois** dans la console Firebase (https://console.firebase.google.com, projet `autocut-eb855`) :

1. **Authentication › Méthode de connexion** : activer **E-mail/Mot de passe** et **Google**.
2. **Authentication › Paramètres › Domaines autorisés** : vérifier `localhost` (ajouter le domaine de
   production au moment de la mise en ligne).
3. **Storage** : créer le bucket s'il n'existe pas, puis publier les règles du fichier `storage.rules`
   (onglet *Règles*, copier-coller, *Publier*) — ou `npx firebase-tools deploy --only storage`.

Les comptes créés avec un nom d'utilisateur reçoivent une adresse technique `nom@users.autocut.invalid`
(Firebase exige un e-mail) : ils ne peuvent donc pas récupérer leur mot de passe par e-mail.

**Tests sans toucher au projet réel** : `npx firebase-tools emulators:start --only auth,storage --project demo-autocut`,
puis lancer le site avec `VITE_FIREBASE_EMULATORS=true` et le backend avec `FIREBASE_PROJECT_ID=demo-autocut`,
`FIREBASE_STORAGE_BUCKET=demo-autocut.appspot.com`, `FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099` et
`FIREBASE_STORAGE_EMULATOR_HOST=127.0.0.1:9199`.

**E-mails en dev** : sans SMTP configuré, les e-mails (mot de passe oublié, montage prêt) ne partent pas :
le lien s'affiche dans la console du backend et le message est enregistré dans `backend/storage/outbox/`.

**Paiement en dev** : sans clés Stripe et avec `DEV_FAKE_PAYMENTS=true`, le bouton « Passer au plan Pro »
active l'offre sans paiement. **À désactiver en production.**

### Tests

```bash
cd backend
pytest                          # 68 tests : moteur (FFmpeg réel), API, worker, recette
pytest --cov=app                # couverture (78 % au total, > 95 % sur silences/sous-titres/rendu/pipeline)

# Test de transcription réelle (télécharge le modèle « tiny ») :
RUN_WHISPER_TESTS=1 WHISPER_SAMPLE_VIDEO=chemin/vers/video_parlee.mp4 pytest tests/test_engine.py
```

```bash
npm run typecheck && npm run build   # frontend
```

### Windows : « Une stratégie de contrôle d'application a bloqué ce fichier »

Si *Smart App Control* bloque une DLL Python au démarrage :

- **SQLAlchemy** : réinstallez la version pur Python
  `set DISABLE_SQLALCHEMY_CEXT=1 && pip install --force-reinstall --no-deps --no-binary sqlalchemy SQLAlchemy`
- **PyAV** (`av`, dépendance de faster-whisper) : rien à faire, le moteur s'en passe automatiquement
  (l'audio est décodé par FFmpeg).

## Mise en production (VPS Linux ~10 €/mois)

```bash
# Sur un Ubuntu 24.04 : utilisateur, dépendances, code dans /opt/autocut
sudo apt install ffmpeg fonts-dejavu fonts-liberation postgresql caddy python3-venv nodejs npm
sudo useradd -r -m -d /opt/autocut autocut
# … copier le dépôt dans /opt/autocut, puis :
npm ci && npm run build                          # produit dist/, servi par FastAPI
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # puis éditer : voir ci-dessous
sudo cp ../deploy/autocut-api.service ../deploy/autocut-worker@.service /etc/systemd/system/
sudo cp ../deploy/Caddyfile /etc/caddy/Caddyfile   # remplacer votre-domaine.com
sudo systemctl enable --now autocut-api autocut-worker@1 caddy
```

Variables `.env` indispensables en production :

```
APP_ENV=production
SECRET_KEY=<chaîne aléatoire de 48+ caractères>
PUBLIC_URL=https://votre-domaine.com
DATABASE_URL=postgresql://autocut:motdepasse@localhost:5432/autocut
EMBEDDED_WORKER=false
DEV_FAKE_PAYMENTS=false
SMTP_HOST=… SMTP_USER=… SMTP_PASSWORD=… MAIL_FROM=…
STRIPE_SECRET_KEY=sk_live_… STRIPE_WEBHOOK_SECRET=whsec_… STRIPE_PRICE_PRO=price_… STRIPE_PRICE_AGENCE=price_…
```

**Stripe** : créez deux produits à prix récurrent mensuel (Pro 7 €, Agence 29 €), reportez leurs `price_…`,
puis ajoutez un webhook vers `https://votre-domaine.com/api/billing/webhook` avec les événements
`checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`.

**Monter en charge** (NF-SCA-01) : `systemctl enable --now autocut-worker@2` (autant d'instances que de
cœurs disponibles / 2), sur la même machine ou une autre machine pointant vers la même base et le même stockage.

**Reprise après coupure** (R10) : les services redémarrent seuls ; un montage interrompu est détecté
(battement de cœur) et remis en file automatiquement, puis marqué en échec avec remboursement après 2 tentatives.

## Mise en ligne gratuite (Netlify) et déploiement continu

L'interface (fichiers statiques) se publie **gratuitement sur Netlify** ; le backend FastAPI continue de
tourner sur une machine (VPS, tunnel Cloudflare, Oracle Cloud *Always Free*, Hugging Face Spaces…) et le
site l'atteint par un proxy `/api/*` — un seul domaine côté navigateur, donc aucune CORS à gérer.

- `.github/workflows/ci.yml` — à chaque poussée et pull request : `npm run typecheck`, `npm run build`,
  puis la suite de tests Python (66 cas : moteur, API, worker, Firebase, paiement) avec FFmpeg réel.
- `.github/workflows/deploy-netlify.yml` — publie `dist/` sur Netlify à chaque poussée sur `main`
  (ou laisse Netlify compiler lui-même le dépôt : intégration Git, aucun secret à gérer).
- `netlify.toml` + `scripts/netlify-postbuild.mjs` — build, en-têtes de sécurité et écriture de
  `dist/_redirects` (proxy `/api/*` vers `API_PROXY_URL`, puis repli SPA).

```bash
npm run en-ligne                                          # backend + tunnel Cloudflare gratuit :
                                                          # affiche l'adresse https à coller dans Netlify
API_PROXY_URL=https://api.votre-domaine.com npm run build  # règle le proxy, puis…
npm run netlify:deploy                                     # publie dist/ sur Netlify
```

Guides : **[docs/METTRE_EN_LIGNE_PAS_A_PAS.md](docs/METTRE_EN_LIGNE_PAS_A_PAS.md)** (simple, 15 minutes,
0 €, rien à installer) et **[docs/DEPLOIEMENT_NETLIFY.md](docs/DEPLOIEMENT_NETLIFY.md)** (version détaillée :
VPS, Oracle *Always Free*, Hugging Face Spaces, Firebase, Stripe, dépannage).

## Shorts

Au moment de lancer un montage, « Type de montage → Shorts » produit plusieurs vidéos courtes au lieu
d'un montage complet : **3 shorts de 30 s par défaut**, de 1 à 10 shorts, chacun de **30 s à 2 min 30**.

- Les extraits sont choisis dans la vidéo déjà débarrassée de ses silences, parmi les passages où la
  parole est la plus dense ; ils commencent au début d'une phrase et s'arrêtent à la fin d'une phrase
  (un short peut donc durer un peu moins que la durée choisie, jamais plus).
- Chaque short a ses sous-titres karaoké, sa musique, son format (9:16 par défaut) et son fichier SRT.
- Sur l'écran de résultat, on change après coup le nombre, la durée ou le type de montage sans
  consommer de crédit : la transcription est réutilisée.
- Une vidéo trop courte pour le nombre demandé donne moins de shorts (indiqué à l'écran).

## Chaîne de traitement

```
Upload par morceaux (reprise possible) ─▶ validation (signature binaire + ffprobe)
  ─▶ file d'attente (priorité Pro/Agence) ─▶ worker :
     [analyse]        ffprobe + silencedetect (−35 dB, 0,5 s) → plages conservées, marge 100 ms,
                      alignées sur les images (aucune dérive audio/vidéo)
     [transcription]  audio coupé → faster-whisper (sous-processus, VAD) → mots horodatés
     [montage]        sous-titres .ass karaoké (6 styles) + .srt + filigrane (offre gratuite)
     [encodage]       1 seule passe FFmpeg : coupe + recadrage + incrustation + musique/ducking
                      → MP4 H.264/AAC 1080p max, faststart (lecture immédiate dans le navigateur)
  ─▶ e-mail « montage prêt » ─▶ aperçu, téléchargements, correction des sous-titres
```

## Couverture du cahier des charges

| Exigence | État |
|---|---|
| F-CPT-01/02/03 comptes (nom d’utilisateur, connexion immédiate), mot de passe oublié, bcrypt | ✅ (confirmation e-mail retirée à la demande de l’équipe) |
| F-CPT-04 connexion Google | ✅ (activer avec GOOGLE_CLIENT_ID) |
| F-CPT-05 profil, préférences mémorisées · F-CPT-06 suppression du compte | ✅ |
| F-UP-01…05 glisser-déposer, MP4/MOV/WebM/MKV 500 Mo, YouTube, rejet clair, reprise | ✅ |
| F-TRT-01…06 silences, respiration, file + e-mail, étapes + %, réglages, remboursement + réessayer | ✅ |
| F-TRT-07 lot (5 en file, offres payantes) | ✅ côté serveur (plusieurs montages en file) |
| F-ST-01…06 Whisper mot à mot, FR/EN auto, karaoké, 6 styles, .srt/.ass, éditeur | ✅ |
| F-HAB-01/02 20 musiques libres + ducking, formats 9:16 / 1:1 / origine | ✅ |
| F-HAB-03 zooms dynamiques · F-HAB-04 logo personnalisé | ⏳ V2 (P3) |
| Shorts (ajout) : 1 à 10 extraits de 30 s à 2 min 30, défaut 3 × 30 s | ✅ |
| F-RES-01…04 aperçu, MP4 H.264/AAC, avant/après, historique 30 j | ✅ |
| F-PAI-01…05 gratuit (2/mois, 5 min, filigrane), Pro, Stripe, compteur, Agence | ✅ (sièges multiples de l'offre Agence : V2) |
| F-WEB-01/02 accueil, tarifs, FAQ, mentions légales, confidentialité, CGU | ✅ (informations légales de l'éditeur à compléter) |
| NF-SEC-01…03 HTTPS (Caddy), vidéos privées (jetons signés), limitation de débit | ✅ |
| NF-MNT-01 Git, tests ≥ 60 % sur le moteur, documentation | ✅ (dépôt Git à initialiser) |

## Performances mesurées

Poste de développement (Windows, 12 cœurs logiques, CPU uniquement), vidéo 1080p parlée en français :

| Vidéo | Modèle | Analyse | Transcription | Encodage 9:16 | Total |
|---|---|---|---|---|---|
| 26 s | small | 4 s | 15 s | 8 s | **27 s** |
| 10 min | base | 7 s | 165 s | 82 s | **≈ 4 min 10** |

La cible NF-PER-01 (10 min en ≤ 3 min) **n'est pas encore atteinte sur CPU** : la transcription représente
deux tiers du temps. Leviers, du plus simple au plus efficace : `WHISPER_MODEL=base` ou `tiny`,
`WHISPER_BEAM_SIZE=1`, un VPS plus puissant, ou un GPU (`WHISPER_DEVICE=cuda`, `WHISPER_COMPUTE_TYPE=float16`)
qui ramène la transcription à quelques secondes. Mesurez sur le serveur de référence avant le lancement.

## Choix techniques

- **File d'attente en base plutôt que Redis + RQ** : RQ ne fonctionne pas sous Windows (dépend de `fork`),
  or l'équipe développe sous Windows. La table `projects` sert de file : prise de job par mise à jour
  atomique, priorité, battement de cœur, reprise automatique. Plusieurs workers peuvent tourner en parallèle.
  Aucun service supplémentaire à installer ni à payer.
- **Transcription dans un sous-processus** : le modèle Whisper (~1 Go) est libéré avant l'encodage
  FFmpeg, ce qui évite les échecs mémoire sur un petit VPS.
- **Musique** : la bibliothèque est générée par synthèse (aucun échantillon externe) et publiée en CC0 ;
  le registre `backend/music/licenses.json` trace chaque piste. Des morceaux Creative Commons externes
  peuvent y être ajoutés avec leur auteur, source et licence.
- **Nom de marque** : l'interface affiche « AutoCut » (maquette) ; le cahier des charges parle de
  « MontageAuto ». Le filigrane et les e-mails utilisent `BRAND_NAME` (défaut `AutoCut`).

## API

Documentation interactive : `http://localhost:8000/api/docs`.
