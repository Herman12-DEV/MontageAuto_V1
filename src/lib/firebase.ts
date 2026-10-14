// Firebase : authentification (Firebase Auth) et stockage des vidéos importées (Storage).
import { initializeApp } from 'firebase/app'
import { getAnalytics, isSupported } from 'firebase/analytics'
import { connectAuthEmulator, getAuth } from 'firebase/auth'
import { connectStorageEmulator, getStorage } from 'firebase/storage'

// Émulateurs locaux (tests) : VITE_FIREBASE_EMULATORS=true. Le projet « demo-… » est isolé
// et n'atteint jamais le projet de production.
const useEmulators = import.meta.env.VITE_FIREBASE_EMULATORS === 'true'

const firebaseConfig = useEmulators
  ? {
      apiKey: 'demo-key',
      authDomain: 'demo-autocut.firebaseapp.com',
      projectId: 'demo-autocut',
      storageBucket: 'demo-autocut.appspot.com',
      appId: 'demo-app',
    }
  : {
      apiKey: 'AIzaSyA_oqHSjaPetGxciYJx2IzBs_ZEGy4YbzM',
      authDomain: 'autocut-eb855.firebaseapp.com',
      projectId: 'autocut-eb855',
      storageBucket: 'autocut-eb855.firebasestorage.app',
      messagingSenderId: '805005090429',
      appId: '1:805005090429:web:098fddd9309a776dd85b14',
      measurementId: 'G-LQMMVH1CJ7',
    }

export const app = initializeApp(firebaseConfig)
export const auth = getAuth(app)
export const storage = getStorage(app)

if (useEmulators) {
  connectAuthEmulator(auth, 'http://127.0.0.1:9099', { disableWarnings: true })
  connectStorageEmulator(storage, '127.0.0.1', 9199)
} else {
  // Mesure d'audience : ignorée si le navigateur ne la permet pas (bloqueur, navigation privée).
  isSupported()
    .then((ok) => {
      if (ok) getAnalytics(app)
    })
    .catch(() => undefined)
}
