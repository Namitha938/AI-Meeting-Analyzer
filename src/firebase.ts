import { initializeApp, getApps, getApp, type FirebaseApp } from 'firebase/app'
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  type Auth,
  type UserCredential,
} from 'firebase/auth'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
}

export function getFirebaseAuth(): { app: FirebaseApp; auth: Auth; googleProvider: GoogleAuthProvider } {
  const existingApps = getApps()
  const app = existingApps.length > 0 ? getApp() : initializeApp(firebaseConfig)
  const auth = getAuth(app)
  const googleProvider = new GoogleAuthProvider()
  googleProvider.setCustomParameters({ prompt: 'select_account' })
  return { app, auth, googleProvider }
}

let defaultInstances: { app: FirebaseApp; auth: Auth; googleProvider: GoogleAuthProvider } | null = null
try {
  defaultInstances = getFirebaseAuth()
} catch (e) {
  console.warn('Firebase lazy init notice:', e)
}

export const app = defaultInstances?.app ?? null
export const auth = defaultInstances?.auth ?? null
export const googleProvider = defaultInstances?.googleProvider ?? null

export async function loginWithGooglePopup(): Promise<{ email: string; full_name: string; uid: string }> {
  const { auth, googleProvider } = getFirebaseAuth()

  // Ensure prompt: 'select_account' is set so the official Google/Firebase popup always opens
  googleProvider.setCustomParameters({ prompt: 'select_account' })

  try {
    const result: UserCredential = await signInWithPopup(auth, googleProvider)
    const user = result.user
    if (!user || !user.email) {
      throw new Error('No email found in Google profile.')
    }
    return {
      email: user.email,
      full_name: user.displayName || user.email.split('@')[0],
      uid: user.uid,
    }
  } catch (err: any) {
    console.warn('Firebase Google Auth popup error/notice:', err)
    if (err.code === 'auth/popup-closed-by-user') {
      const e: any = new Error('Google sign-in was closed by user.')
      e.code = err.code
      throw e
    }
    if (err.code === 'auth/cancelled-popup-request') {
      const e: any = new Error('Previous popup request was cancelled. Please try again.')
      e.code = err.code
      throw e
    }
    if (err.code === 'auth/popup-blocked') {
      const e: any = new Error('Google popup was blocked by your browser. Please allow popups for this site.')
      e.code = err.code
      throw e
    }
    if (err.code === 'auth/operation-not-allowed') {
      const e: any = new Error('Google sign-in is not enabled in your Firebase Console.')
      e.code = err.code
      throw e
    }
    if (err.code === 'auth/unauthorized-domain') {
      const e: any = new Error('This domain is not in Firebase authorized domains.')
      e.code = err.code
      throw e
    }
    throw err
  }
}

export async function loginWithGoogleRedirect(): Promise<void> {
  const { auth, googleProvider } = getFirebaseAuth()
  googleProvider.setCustomParameters({ prompt: 'select_account' })
  await signInWithRedirect(auth, googleProvider)
}

export async function checkRedirectResult(): Promise<{ email: string; full_name: string; uid: string } | null> {
  try {
    const { auth } = getFirebaseAuth()
    const result = await getRedirectResult(auth)
    if (result && result.user && result.user.email) {
      return {
        email: result.user.email,
        full_name: result.user.displayName || result.user.email.split('@')[0],
        uid: result.user.uid,
      }
    }
  } catch (err) {
    console.warn('Redirect auth check notice:', err)
  }
  return null
}
