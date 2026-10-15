# Mettre AutoCut en ligne, pas à pas (0 €)

Guide volontairement simple. Tu n'as **rien à installer de plus**, rien à payer, et tu ne touches pas au code.

---

## 1. L'image à retenir (pour comprendre)

- **Netlify = la vitrine.** C'est le site que les gens voient (l'interface). Il est **gratuit** et **toujours allumé**.
- **Ton ordinateur = le four.** C'est lui qui fabrique les vidéos (FFmpeg + Whisper). Ça demande du temps
  de calcul : Netlify ne sait pas le faire, et aucun hébergeur gratuit ne le fera à ta place.
- **Le tunnel Cloudflare = le passe-plat.** Il donne une adresse Internet https à ton « four »,
  gratuitement, sans compte et sans carte bancaire.

```
Visiteur → Netlify (la vitrine, toujours en ligne)
                │
                └── /api/… ──→ ton ordinateur (le four) via le tunnel Cloudflare
                                     └── Firebase (comptes + vidéos importées)
```

**Conséquence à accepter :** tant que ton ordinateur est éteint, le site s'affiche mais les montages ne
marchent pas. Le § 8 explique comment régler ça plus tard (toujours gratuit ou presque).

---

## 2. Avant de commencer : vérifie ces 3 cases

- [ ] Node.js est installé (`node -v` doit répondre `v22…`) — tu l'as déjà puisque `npm start` marche.
- [ ] Le backend est déjà installé une fois : le dossier `backend/.venv` existe
      (sinon : `cd backend` puis `python -m venv .venv` puis `.venv\Scripts\pip install -r requirements.txt` sous Windows).
- [ ] Tu as un compte GitHub (oui, puisque ton code y est : `Herman12-DEV`).

---

## 3. Étape 1 — Allumer ton serveur (2 minutes)

Dans un terminal, à la racine du projet :

```bash
npm run en-ligne
```

Ce qui se passe tout seul :

1. le backend démarre sur ton port 8000 ;
2. un tunnel Cloudflare s'ouvre ;
3. cette information s'affiche :

```
  L'API AutoCut est en ligne :  https://quelque-chose.trycloudflare.com
```

👉 **Copie cette adresse** (elle sert à l'étape 5) et **teste-la dans ton navigateur** en ajoutant `/api/health` :

```
https://quelque-chose.trycloudflare.com/api/health
```

Tu dois voir du texte en JSON : `{"status":"ok", ...}`. Si tu vois ça, ton serveur est bien en ligne. ✅

> ⚠️ **Ne ferme pas cette fenêtre** et ne mets pas l'ordinateur en veille : c'est ton serveur.
> Ctrl + C arrête tout. À chaque redémarrage, l'adresse change : refais l'étape 5.

---

## 4. Étape 2 — Créer le site sur Netlify (5 minutes, une seule fois)

1. Va sur **https://app.netlify.com** → *Sign up* → **« Sign up with GitHub »** (accepte l'autorisation).
2. Clique sur **Add new site** → **Import an existing project**.
3. Choisis **GitHub** → autorise Netlify à lire tes dépôts → clique sur **MontageAuto_V1**.
4. Netlify lit tout seul le fichier `netlify.toml` du dépôt. Tu dois voir :
   - *Branch to deploy* : `main`
   - *Build command* : `npm run build`
   - *Publish directory* : `dist`
5. Clique sur **Deploy**. Au bout d'une minute, Netlify donne une adresse du type
   **https://montageauto.netlify.app**. Le site s'affiche déjà… mais il ne peut pas encore parler
   à ton serveur : c'est l'étape suivante.

> Note : à ce stade, `main` ne contient pas encore la configuration Netlify (elle est dans la
> **pull request n° 3**). Le déploiement fonctionnera pleinement après sa fusion — voir le § 9.

---

## 5. Étape 3 — Brancher la vitrine sur ton serveur (1 minute)

Dans Netlify :

1. **Site configuration** → **Environment variables** → **Add a variable** :
   - *Key* : `API_PROXY_URL`
   - *Value* : l'adresse copiée à l'étape 3 (ex. `https://quelque-chose.trycloudflare.com`)
     — **sans** `/api` à la fin, **sans** barre oblique finale.
2. **Deploys** → **Trigger deploy** → **Clear cache and deploy site**.

Netlify reconstruit le site en indiquant à ton site : « les appels `/api/…` vont vers cette adresse ».
C'est pour ça qu'il n'y a **aucun problème de CORS** : pour le navigateur, tout est sur le même domaine.

---

## 6. Étape 4 — Autoriser Netlify dans Firebase (3 minutes)

Sans ça, la création de compte échouera avec le message `auth/unauthorized-domain`.

1. Va sur **https://console.firebase.google.com** → projet **autocut-eb855**.
2. Menu **Authentication** → onglet **Settings** → section **Authorized domains** → **Add domain**.
3. Ajoute ton adresse Netlify **sans** `https://` (l’adresse de ton site : `montageauto.netlify.app`) → **Add**.
4. (Uniquement si tu veux « Continuer avec Google ») : https://console.cloud.google.com → *API et
   services* → *Identifiants* → ton **ID client OAuth** → *Origines JavaScript autorisées* →
   ajoute `https://montageauto-v1.netlify.app` → *Enregistrer*.

---

## 7. Étape 5 — Vérifier que tout passe ✅

Sur ton site Netlify :

1. La page d'accueil s'affiche en HTTPS.
2. **Créer un compte** (nom d'utilisateur + mot de passe) : tu es connecté tout de suite.
3. Le tableau de bord affiche le moteur **en ligne** (pastille verte). Rouge = l'étape 5 ou l'étape 3
   est à refaire.
4. Dépose une petite vidéo : elle passe de « analyse » à « transcription » puis « montage », et le
   résultat est téléchargeable.
5. Sur ton téléphone, le format 9:16 s'affiche bien.

---

## 8. Plus tard : faire tourner le serveur sans ton ordinateur

| Solution | Prix | Points forts | Points faibles |
|---|---|---|---|
| **Ton PC + tunnel Cloudflare** (ce guide) | 0 € | Rien à payer, rien à louer | Le PC doit rester allumé ; adresse qui change |
| **VPS loué** (5 €/mois) | 5 €/mois | Toujours allumé, rapide, HTTPS définitif | Payant |
| **Oracle Cloud « Always Free »** | 0 € à vie | VM 4 cœurs / 24 Go, reste allumée | Demande une carte bancaire pour vérifier l'identité |
| **Hugging Face Spaces (Docker)** | 0 € | Beaucoup de RAM, mise en ligne facile | S'endort sans visite, disque effacé à chaque redémarrage |

Le pas-à-pas de ces solutions est dans **[DEPLOIEMENT_NETLIFY.md](DEPLOIEMENT_NETLIFY.md)** (§ 4).

---

## 9. Adresse de ton site

Ton site est déjà en ligne : **https://montageauto.netlify.app** (je l’ai ouvert : l’interface s’affiche).
Ce qui manque encore, c’est le lien avec le serveur : aujourd’hui `https://montageauto.netlify.app/api/health`
répond « Page not found », parce que la configuration du proxy (celle de la pull request n° 3) n’est pas
encore dans `main`. Après la fusion de la PR n° 3, il ne restera que les étapes 1, 3 et 4 de ce guide.

## 10. Ensuite : publier une nouvelle version du site

- Dès que la **pull request n° 3** est fusionnée dans `main`, Netlify republie le site **à chaque
  `git push` sur `main`**, tout seul. Tu n'as plus jamais à faire « deploy » à la main.
- Avant chaque publication, GitHub Actions teste tout (site + 66 tests Python). Le résultat est visible
  dans l'onglet **Actions** du dépôt : vert = tout va bien, rouge = le déploiement est à éviter.

---

## 11. Si ça ne marche pas — les 4 pannes les plus courantes

| Ce que tu vois | Ce qui se passe | Quoi faire |
|---|---|---|
| « Le site ne parvient pas à joindre le serveur AutoCut » | Le site ne sait pas où est ton serveur | Étape 5 : `API_PROXY_URL` + *Clear cache and deploy* |
| Connexion impossible, message `auth/unauthorized-domain` | Firebase ne connaît pas l'adresse Netlify | Étape 6 |
| La page `/api/health` du tunnel ne répond plus | La fenêtre du tunnel est fermée, ou le PC a redémarré | Relance `npm run en-ligne`, puis étape 5 avec la **nouvelle** adresse |
| « Build failed » dans Netlify | Le site ne compile pas | Dis-le-moi : la CI reproduit l'erreur, on la corrige ensemble |

---

## 12. Quels fichiers du dépôt servent à quoi (pour info)

| Fichier | Rôle |
|---|---|
| `scripts/en-ligne.mjs` | Le contenu de la commande `npm run en-ligne` (backend + tunnel + adresse à copier) |
| `netlify.toml` | Les réglages du build Netlify (commande, dossier `dist`, en-têtes de sécurité) |
| `scripts/netlify-postbuild.mjs` | Écrit `dist/_redirects` : envoie `/api/*` vers ton serveur, le reste vers le site |
| `.github/workflows/ci.yml` | Les tests automatiques à chaque modification (`npm run typecheck`, build, 66 tests Python) |
| `.github/workflows/deploy-netlify.yml` | La publication automatique du site sur Netlify |
| `docs/DEPLOIEMENT_NETLIFY.md` | La version détaillée de ce guide (VPS, Oracle, Hugging Face, Stripe, e-mails…) |
