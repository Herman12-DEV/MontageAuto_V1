import type { ReactNode } from 'react'
import { ArrowRight } from 'lucide-react'
import SiteFooter from './SiteFooter'

type Item = { title: string; text: ReactNode; dark?: boolean; num?: string }

type Info = {
  tag: string
  title: ReactNode
  lead?: string
  items?: Item[]
  sections?: { heading: string; body: ReactNode }[]
  cta?: boolean
}

// Informations à fournir par l’équipe porteuse avant la mise en ligne (§1.3 du cahier des charges).
const EDITOR = '[À compléter : raison sociale, forme juridique, adresse, RCCM]'
const CONTACT = '[À compléter : adresse e-mail de contact]'

export const infoPages: Record<string, Info> = {
  '/tarifs': {
    tag: 'Tarifs',
    title: (
      <>
        Un prix juste.
        <br />
        Sans surprise.
      </>
    ),
    lead: 'Commencez gratuitement. Passez au Pro quand vous publiez plus.',
    items: [
      {
        num: '0 €',
        title: 'Gratuit',
        text: '2 montages par mois · vidéos jusqu’à 5 min · sous-titres karaoké · filigrane AutoCut · file standard.',
      },
      {
        num: '7 €',
        title: 'Pro — par mois',
        text: 'Montages illimités · vidéos jusqu’à 30 min · sans filigrane · file prioritaire · export SRT/ASS.',
        dark: true,
      },
      {
        num: '29 €',
        title: 'Agence — par mois',
        text: 'Tout le Pro · traitement par lot (5 vidéos en file) · support prioritaire.',
      },
    ],
    cta: true,
  },
  '/faq': {
    tag: 'Questions fréquentes',
    title: (
      <>
        Vos questions.
        <br />
        Nos réponses.
      </>
    ),
    items: [
      {
        title: 'Que fait AutoCut exactement ?',
        text: 'Il supprime les silences, ajoute des sous-titres mot par mot, une musique dosée sous la voix et recadre au format vertical, automatiquement.',
      },
      {
        title: 'Quels formats sont acceptés ?',
        text: 'MP4, MOV, WebM et MKV jusqu’à 500 Mo, ou un lien YouTube dont vous détenez les droits. Export en MP4 H.264, 1080p maximum.',
      },
      {
        title: 'Combien de temps faut-il ?',
        text: 'Quelques minutes : une vidéo de 10 min est traitée en 3 min environ. Vous pouvez fermer la page, nous vous prévenons par e-mail.',
      },
      {
        title: 'Les sous-titres sont-ils fiables ?',
        text: 'La transcription (Whisper) dépasse 95 % de précision sur une parole claire en français et en anglais. Vous pouvez corriger chaque phrase avant de télécharger.',
      },
      {
        title: 'Mes vidéos sont-elles privées ?',
        text: 'Oui. Elles ne sont accessibles qu’à vous, traitées sur nos serveurs (aucun service tiers) et supprimées automatiquement après 30 jours.',
      },
      {
        title: 'Et si un montage échoue ?',
        text: 'Le crédit est remboursé automatiquement et un bouton « Réessayer » relance le traitement.',
      },
    ],
  },
  '/mentions-legales': {
    tag: 'Mentions légales',
    title: 'Mentions légales.',
    sections: [
      { heading: 'Éditeur', body: `Le service AutoCut est édité par ${EDITOR}. Contact : ${CONTACT}.` },
      { heading: 'Hébergement', body: '[À compléter : nom et adresse de l’hébergeur du serveur (VPS).]' },
      {
        heading: 'Propriété intellectuelle',
        body: 'La marque, l’interface et le code d’AutoCut sont protégés. Les vidéos téléversées restent la propriété de leurs auteurs.',
      },
      {
        heading: 'Musiques',
        body: 'La bibliothèque musicale intégrée est exclusivement composée de morceaux libres de droits. Le registre des licences est tenu à jour et disponible sur demande.',
      },
    ],
  },
  '/confidentialite': {
    tag: 'Confidentialité',
    title: (
      <>
        Vos données.
        <br />
        Vos droits.
      </>
    ),
    sections: [
      {
        heading: 'Cadre légal',
        body: 'Le traitement respecte la loi ivoirienne n° 2013-450 relative à la protection des données à caractère personnel (autorité de contrôle : ARTCI) et, pour les utilisateurs européens, le RGPD.',
      },
      {
        heading: 'Données collectées',
        body: 'Adresse e-mail, nom, mot de passe (stocké haché, jamais en clair), préférences, vidéos téléversées et leurs transcriptions. Les paiements sont traités par Stripe : nous ne voyons jamais votre numéro de carte.',
      },
      {
        heading: 'Finalité',
        body: 'Uniquement fournir le service de montage : aucune revente, aucun usage publicitaire, aucun envoi des vidéos à un service tiers de transcription.',
      },
      {
        heading: 'Durée de conservation',
        body: 'Vidéos, rendus et transcriptions sont supprimés automatiquement 30 jours après leur dépôt. Le compte et toutes ses données sont supprimés immédiatement à votre demande.',
      },
      {
        heading: 'Vos droits',
        body: `Depuis « Mon profil », vous pouvez télécharger toutes vos données (droit d’accès) et supprimer votre compte en un clic (droit à l’effacement). Pour toute autre demande : ${CONTACT}.`,
      },
      {
        heading: 'Cookies',
        body: 'Aucun cookie publicitaire ni traceur. Seul un jeton de session est conservé dans votre navigateur pour vous garder connecté.',
      },
    ],
  },
  '/cgu': {
    tag: 'Conditions générales d’utilisation',
    title: 'CGU.',
    sections: [
      {
        heading: 'Objet',
        body: 'AutoCut est une plateforme de montage vidéo automatique : suppression des silences, sous-titres, musique et recadrage.',
      },
      {
        heading: 'Traitement automatisé',
        body: 'Le montage et les sous-titres sont produits automatiquement par des outils d’intelligence artificielle (FFmpeg et Whisper), sans intervention humaine. Le résultat peut comporter des erreurs : vérifiez-le avant publication.',
      },
      {
        heading: 'Droits sur les contenus',
        body: 'En téléversant une vidéo ou en indiquant un lien YouTube, vous déclarez détenir tous les droits nécessaires sur ce contenu. Tout contenu illégal, haineux ou portant atteinte aux droits d’autrui est interdit et entraîne la suppression du compte.',
      },
      {
        heading: 'Offres et paiement',
        body: 'L’offre gratuite inclut 2 montages par mois. Les offres payantes sont des abonnements mensuels sans engagement, résiliables à tout moment depuis votre profil. Un crédit consommé par un montage en échec est remboursé automatiquement.',
      },
      {
        heading: 'Disponibilité',
        body: 'Nous visons 99 % de disponibilité mensuelle mais ne pouvons garantir un service ininterrompu. Les fichiers sont conservés 30 jours : téléchargez vos rendus.',
      },
      { heading: 'Contact', body: `Pour toute question : ${CONTACT}.` },
    ],
  },
}

export default function InfoPage({ path }: { path: string }) {
  const page = infoPages[path]
  return (
    <div className="landing">
      <header className="hero hero--compact">
        <div className="container hero__top">
          <a className="brand" href="#/">
            AutoCut
          </a>
          <nav className="hero__nav">
            <a href="#/tarifs">Tarifs</a>
            <a href="#/faq">FAQ</a>
            <a href="#/connexion">Connexion</a>
          </nav>
        </div>
      </header>
      <section className="section">
        <div className="container">
          <div className="section__head">
            <span className="tag">{page.tag}</span>
          </div>
          <div className="split">
            <h1 className="title">{page.title}</h1>
            {page.lead && <p className="lead">{page.lead}</p>}
          </div>
          {page.items && (
            <div className="feature-list info__list">
              {page.items.map((item, i) => (
                <article className={`feature${item.dark ? ' feature--dark' : ''}`} key={item.title}>
                  <span className="tag feature__num">{item.num ?? String(i + 1).padStart(2, '0')}</span>
                  <div>
                    <h3>{item.title}</h3>
                    <p>{item.text}</p>
                  </div>
                </article>
              ))}
            </div>
          )}
          {page.sections && (
            <div className="prose">
              {page.sections.map((section) => (
                <section key={section.heading}>
                  <h2>{section.heading}</h2>
                  <p>{section.body}</p>
                </section>
              ))}
            </div>
          )}
          {page.cta && (
            <p className="info__cta">
              <a className="btn btn--dark" href="#/inscription">
                Essayer gratuitement
                <ArrowRight size={15} />
              </a>
            </p>
          )}
        </div>
      </section>
      <SiteFooter />
    </div>
  )
}
