import { useState, useEffect } from 'react';
import { signInWithEmailAndPassword, signInWithPopup, onAuthStateChanged } from 'firebase/auth';
import { auth, googleProvider } from './firebase';
import { useNavigate, Link } from 'react-router-dom';
import PasswordInput from './PasswordInput';

function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [user, setUser] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
    });
    return () => unsubscribe();
  }, []);

  const login = async () => {
    try {
      await signInWithEmailAndPassword(auth, email.trim(), password);
      alert("Logged in successfully!");
      navigate('/dashboard');
    } catch (e) {
      alert("❌ Login failed: " + e.message);
      console.error("Login error:", e);
    }
  };

  const loginWithGoogle = async () => {
    try {
      await signInWithPopup(auth, googleProvider);
      alert("Logged in with Google!");
      navigate('/dashboard');
    } catch (e) {
      alert("❌ Google login failed: " + e.message);
    }
  };

  return (
    <div style={{ padding: '2rem' }}>
      <h2>Login</h2>
      <input
        type="email"
        placeholder="Email"
        value={email}
        onChange={e => setEmail(e.target.value)}
      />
      <PasswordInput password={password} setPassword={setPassword} />
      <br /><br />
      <button onClick={login}>Log In</button>
      <br /><br />
      <button onClick={loginWithGoogle}>Sign in with Google</button>
      {!user && (
        <p>
          Don't have an account? <Link to="/signup">Sign Up</Link>
        </p>
      )}
    </div>
  );
}

export default LoginPage;
