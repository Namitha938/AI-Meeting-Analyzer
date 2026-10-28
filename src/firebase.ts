import { initializeApp, getApps, getApp } from 'firebase/app'
import { getAuth, GoogleAuthProvider, signInWithPopup, UserCredential } from 'firebase/auth'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
}

const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp()
export const auth = getAuth(app)
export const googleProvider = new GoogleAuthProvider()
googleProvider.setCustomParameters({ prompt: 'select_account' })

export async function loginWithGooglePopup(): Promise<{ email: string; full_name: string; uid: string }> {
  try {
    const result: UserCredential = await signInWithPopup(auth, googleProvider)
    const user = result.user
    if (!user.email) {
      throw new Error('No email found in Google profile.')
    }
    return {
      email: user.email,
      full_name: user.displayName || user.email.split('@')[0],
      uid: user.uid,
    }
  } catch (err: any) {
    console.warn('Firebase popup sign-in encountered an issue:', err)
    if (err.code === 'auth/popup-closed-by-user' || err.code === 'auth/cancelled-popup-request') {
      const e: any = new Error('Google sign-in was cancelled.')
      e.code = err.code
      throw e
    }
    if (err.code === 'auth/operation-not-allowed') {
      const e: any = new Error('Google sign-in is not enabled in your Firebase Console. Please enable "Google" under Firebase Console > Authentication > Sign-in method.')
      e.code = err.code
      throw e
    }
    if (err.code === 'auth/unauthorized-domain') {
      const e: any = new Error('This domain (localhost) is not in Firebase authorized domains. Please add localhost in Firebase Console > Authentication > Settings > Authorized domains.')
      e.code = err.code
      throw e
    }
    if (err.code === 'auth/popup-blocked') {
      const e: any = new Error('Popup was blocked by your browser. Please allow popups for localhost or use the Google selector.')
      e.code = err.code
      throw e
    }
    throw err
  }
}
