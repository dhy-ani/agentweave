import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider, connectAuthEmulator } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';

const useEmulator = process.env.REACT_APP_USE_AUTH_EMULATOR === 'true';

// Firebase "demo-" projects work fully offline against the local emulator, so
// contributors can run the app without access to the real Firebase project.
const firebaseConfig = useEmulator
  ? { apiKey: 'demo-api-key', authDomain: 'localhost', projectId: 'demo-agentweave' }
  : {
      apiKey:            process.env.REACT_APP_FIREBASE_API_KEY,
      authDomain:        process.env.REACT_APP_FIREBASE_AUTH_DOMAIN,
      projectId:         process.env.REACT_APP_FIREBASE_PROJECT_ID,
      storageBucket:     process.env.REACT_APP_FIREBASE_STORAGE_BUCKET,
      messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID,
      appId:             process.env.REACT_APP_FIREBASE_APP_ID,
    };

const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);
if (useEmulator) {
  connectAuthEmulator(auth, process.env.REACT_APP_AUTH_EMULATOR_URL || 'http://127.0.0.1:9099', { disableWarnings: true });
}
export const googleProvider = new GoogleAuthProvider();
export const db = getFirestore(app);
