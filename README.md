# AutoCut — interface frontend

Prototype frontend responsive d’une plateforme de montage vidéo automatique, inspiré de la maquette fournie. L’application est construite avec la commande standard Vite et se limite volontairement au navigateur : aucun backend, compte utilisateur, traitement vidéo ou paiement réel n’est connecté.

## Stack

- React 19 + TypeScript
- Vite 8
- CSS natif (design responsive, sans framework de styles)
- Lucide React pour les icônes
- Node.js 22.12+ et npm

## Démarrage

```bash
npm install
npm run dev
```

Pour vérifier et compiler la version de production :

```bash
npm run typecheck
npm run build
npm run preview
```

## Écrans du prototype

- Page vitrine AutoCut (promesse, fonctionnalités, étapes, états du système et appel à l’action)
- Inscription et connexion (formulaires de démonstration)
- Tableau de bord et cartes de projets
- Nouveau montage (sélection/dépôt de fichier et progression simulée)
- Aperçu de fin de montage et options d’export simulées
- Profil, abonnement de démonstration et réglages interactifs

Les actions locales sont présentes pour parcourir la maquette, mais les vidéos ne sont pas envoyées ni montées : les comptes, l’authentification, les exports, les abonnements et la progression sont uniquement simulés côté frontend.
