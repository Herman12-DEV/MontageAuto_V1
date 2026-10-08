# MontageAuto

Plateforme web de montage vidéo automatique, pensée d'abord pour les créateurs francophones. Cette première livraison pose une interface responsive et interactive pour explorer le parcours de création.

## Stack technique actualisée

### Interface livrée

- **React 19.3.0** avec **TypeScript 6.0** : composants typés et interface maintenable.
- **Vite 8.3.4** : serveur de développement rapide et build optimisé.
- **Lucide React 1.53** : icônes cohérentes et accessibles.
- **CSS natif** : design system léger, sans dépendance de styles à l'exécution.
- **Node.js 22.12+** pour le développement.

### Stack cible pour le service de production

La séparation front/API/worker suit le cahier des charges et permet de faire évoluer le nombre de workers sans refondre l'interface :

- **API** : Python 3.13+, FastAPI 0.143, Pydantic 2.14 et Uvicorn 0.54.
- **Données** : PostgreSQL, SQLAlchemy 2.1 et Alembic 1.20 ; SQLite possible pour le développement local.
- **Jobs asynchrones** : Redis 8 + RQ 2.12 (migration vers Celery uniquement si les besoins de routage/planification le justifient).
- **Traitement média** : FFmpeg + `faster-whisper` 1.2.1 en CPU/int8 ; stockage local en développement, S3 compatible en production.
- **Sécurité et paiements** : mots de passe Argon2id, sessions sécurisées côté serveur, Stripe et URLs de stockage privées/signées.
- **Tests prévus** : Vitest/Testing Library côté interface ; Pytest côté API et moteur (à ajouter avec le backend).

Les versions du backend et les images Docker devront être verrouillées dans les manifests de déploiement avant la mise en production. Les versions du frontend sont déclarées dans `package.json` et `package-lock.json`.

## Démarrage

Prérequis : Node.js 22.12+ et npm.

```bash
npm install
npm run dev
```

L'application sera disponible sur l'URL indiquée par Vite. Le serveur écoute sur `0.0.0.0` pour fonctionner dans un environnement de prévisualisation.

```bash
npm run typecheck
npm run build
npm run preview
```

## Périmètre de cette livraison

L'interface reprend la maquette fournie : identité noire/ivoire avec accent vert, page vitrine, écrans de création de compte et connexion, tableau de bord sombre, projets, nouveau montage, aperçu/export et profil/abonnement. Le formulaire de montage propose dépôt de fichier (MP4, MOV, WebM, MKV, 500 Mo max), import YouTube simulé, format, langue, style de sous-titres et musique de fond.

**Mode prototype :** aucune vidéo n'est envoyée à un serveur, aucun montage ni paiement réel n'est effectué. Le parcours de progression est une simulation locale, indiquée dans l'interface. L'API FastAPI, l'authentification, le worker FFmpeg/Whisper, les courriels et Stripe restent à raccorder avant toute mise en production. La validation finale du conteneur vidéo doit être faite côté serveur (par exemple avec `ffprobe`) ; la validation navigateur ne remplace pas le contrôle de sécurité requis par R9.
