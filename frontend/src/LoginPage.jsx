import { useState } from 'react';
import { signInWithEmailAndPassword, signInWithPopup } from 'firebase/auth';
import { auth, googleProvider } from './firebase';
import { onAuthStateChanged } from 'firebase/auth';
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link } from "react-router-dom";
import PasswordInput from './PasswordInput';

function LoginPage() {

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const [user, setUser] = useState(null);


  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
    });
    return () => unsubscribe();
  }, []);

  {!user && (
    <p>
      Don't have an account? <Link to="/signup">Sign Up</Link>
    </p>
  )}

  useEffect(() => {
  onAuthStateChanged(auth, (user) => {
    if (user) {
      console.log("User is logged in:", user.email);
    } else {
      console.log("No user is logged in");
    }
    });
    }, []);

  const login = async () => {
    try {
      await signInWithEmailAndPassword(auth, email, password);
      alert("Logged in successfully!");
      navigate('/dashboard');
    } catch (e) {
      alert(e.message);
    }
  };

  const loginWithGoogle = async () => {
    try {
      await signInWithPopup(auth, googleProvider);
      alert("Logged in with Google!");
      navigate('/dashboard');
      
    } catch (e) {
      alert(e.message);
    }
  };

  
  return (
    <div style={{ padding: '2rem' }}>
      <h2>Login</h2>
      <input placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} />
      <PasswordInput password={password} setPassword={setPassword} />
      <br /><br />
      <button onClick={login}>Log In</button>
      <br /><br />
      <button onClick={loginWithGoogle}>Sign in with Google</button>
    </div>
  );


}


export default LoginPage;
