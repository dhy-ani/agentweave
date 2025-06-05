import { useState } from 'react';
import { createUserWithEmailAndPassword } from 'firebase/auth';
import { auth } from './firebase';
import { useNavigate } from 'react-router-dom';
import PasswordInput from './PasswordInput';


function SignupPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  const signup = async () => {
    try {
      await createUserWithEmailAndPassword(auth, email, password);
      alert("Signup successful!");
      navigate('/login');
    } catch (e) {

          if (e.code === 'auth/email-already-in-use') {
            alert("An account with this email already exists.");
            navigate('/login');
          } 
          else {
            alert(e.message);
          }
    }
  };

  return (
    <div style={{ padding: '2rem' }}>
      <h2>Sign Up</h2>
      <input placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} />
      <PasswordInput password={password} setPassword={setPassword} />
      <br /><br />
      <button onClick={signup}>Create Account</button>
    </div>
  );
}

export default SignupPage;
