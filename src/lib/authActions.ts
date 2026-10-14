// Actions de connexion Firebase Auth et messages d'erreur en français.
import {
  EmailAuthProvider,
  GoogleAuthProvider,
  createUserWithEmailAndPassword,
  deleteUser,
  reauthenticateWithCredential,
  reauthenticateWithPopup,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  updatePassword,
  updateProfile,
} from 'firebase/auth'
import { auth } from './firebase'

// Firebase exige un e-mail : un nom d'utilisateur est converti en adresse technique.
// Le domaine « .invalid » est réservé (RFC 2606) : aucune boîte réelle ne peut le recevoir.
export const PSEUDO_EMAIL_DOMAIN = 'users.autocut.invalid'
export const USERNAME_RE = /^[a-z0-9][a-z0-9._-]{2,29}$/

export function normalizeUsername(value: string) {
  return value.trim().toLowerCase()
}

export function toAuthEmail(identifier: string): string {
  const value = identifier.trim()
  return value.includes('@') ? value.toLowerCase() : `${normalizeUsername(value)}@${PSEUDO_EMAIL_DOMAIN}`
}

export function isPseudoEmail(email: string | null | undefined) {
  return Boolean(email?.endsWith(`@${PSEUDO_EMAIL_DOMAIN}`))
}

export class AuthError extends Error {}

export function authErrorMessage(error: unknown): string {
  if (error instanceof AuthError) return error.message
  const code = (error as { code?: string })?.code ?? ''
  switch (code) {
    case 'auth/email-already-in-use':
      return 'Ce nom d’utilisateur est déjà pris. Choisissez-en un autre.'
    case 'auth/invalid-credential':
    case 'auth/wrong-password':
    case 'auth/user-not-found':
    case 'auth/invalid-login-credentials':
      return 'Nom d’utilisateur ou mot de passe incorrect.'
    case 'auth/invalid-email':
      return 'Nom d’utilisateur ou e-mail invalide.'
    case 'auth/weak-password':
      return 'Le mot de passe doit contenir au moins 8 caractères.'
    case 'auth/too-many-requests':
      return 'Trop de tentatives. Patientez quelques minutes avant de réessayer.'
    case 'auth/popup-closed-by-user':
    case 'auth/cancelled-popup-request':
      return 'Connexion Google annulée.'
    case 'auth/popup-blocked':
      return 'La fenêtre Google a été bloquée par le navigateur. Autorisez les fenêtres pop-up.'
    case 'auth/operation-not-allowed':
      return 'Ce mode de connexion n’est pas activé dans la console Firebase (Authentication › Méthode de connexion).'
    case 'auth/unauthorized-domain':
      return 'Ce site n’est pas autorisé dans Firebase (Authentication › Paramètres › Domaines autorisés).'
    case 'auth/network-request-failed':
      return 'Connexion à Firebase impossible. Vérifiez votre accès à Internet.'
    case 'auth/requires-recent-login':
      return 'Par sécurité, reconnectez-vous puis recommencez.'
    default:
      return 'La connexion a échoué. Réessayez.'
  }
}

export async function registerWithUsername(username: string, password: string) {
  const name = normalizeUsername(username)
  if (!USERNAME_RE.test(name)) {
    throw new AuthError('Nom d’utilisateur invalide : 3 à 30 caractères (lettres, chiffres, point, tiret ou tiret bas).')
  }
  if (password.length < 8) throw new AuthError('Le mot de passe doit contenir au moins 8 caractères.')
  const credential = await createUserWithEmailAndPassword(auth, toAuthEmail(name), password)
  await updateProfile(credential.user, { displayName: username.trim() })
  // Nouveau jeton incluant le nom affiché, pour la création du compte côté serveur.
  await credential.user.getIdToken(true)
  return credential.user
}

export async function loginWithPassword(identifier: string, password: string) {
  return (await signInWithEmailAndPassword(auth, toAuthEmail(identifier), password)).user
}

export async function loginWithGoogle() {
  const provider = new GoogleAuthProvider()
  provider.setCustomParameters({ prompt: 'select_account' })
  return (await signInWithPopup(auth, provider)).user
}

export async function sendReset(identifier: string) {
  const email = toAuthEmail(identifier)
  if (isPseudoEmail(email)) {
    throw new AuthError(
      'Les comptes créés avec un nom d’utilisateur n’ont pas d’adresse e-mail : la récupération par e-mail est impossible. Connectez-vous avec Google ou créez un nouveau compte.',
    )
  }
  await sendPasswordResetEmail(auth, email)
}

function hasPasswordProvider() {
  return Boolean(auth.currentUser?.providerData.some((p) => p.providerId === 'password'))
}

export function canChangePassword() {
  return hasPasswordProvider()
}

/** Confirme l'identité avant une action sensible (mot de passe ou nouvelle connexion Google). */
async function reauthenticate(password?: string) {
  const user = auth.currentUser
  if (!user) throw new AuthError('Session expirée. Reconnectez-vous.')
  if (hasPasswordProvider()) {
    if (!password) throw new AuthError('Saisissez votre mot de passe actuel.')
    await reauthenticateWithCredential(user, EmailAuthProvider.credential(user.email ?? '', password))
  } else {
    await reauthenticateWithPopup(user, new GoogleAuthProvider())
  }
  return user
}

export async function changePassword(current: string, next: string) {
  if (next.length < 8) throw new AuthError('Le nouveau mot de passe doit contenir au moins 8 caractères.')
  const user = await reauthenticate(current)
  await updatePassword(user, next)
}

export async function changeDisplayName(name: string) {
  if (auth.currentUser) await updateProfile(auth.currentUser, { displayName: name })
}

/** Supprime définitivement le compte Firebase (après les données serveur et le Storage). */
export async function deleteFirebaseAccount(password?: string) {
  const user = await reauthenticate(password)
  await deleteUser(user)
}

export async function confirmIdentity(password?: string) {
  await reauthenticate(password)
}

/** Supprime le compte Firebase courant (identité déjà confirmée juste avant). */
export async function deleteCurrentUser() {
  if (auth.currentUser) await deleteUser(auth.currentUser)
}

export function signInMethods(): string[] {
  const providers = auth.currentUser?.providerData.map((p) => p.providerId) ?? []
  return [providers.includes('password') && 'Nom d’utilisateur et mot de passe', providers.includes('google.com') && 'Google'].filter(
    Boolean,
  ) as string[]
}
