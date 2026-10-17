import { useState } from 'react';
import { createUserWithEmailAndPassword } from 'firebase/auth';
import { auth } from './firebase';
import { useNavigate, Link } from 'react-router-dom';
import PasswordInput from './PasswordInput';
import DoodleAccents from './components/DoodleAccents';
import { authErrorMessage } from './lib/authErrors';

function SignupPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const signup = async () => {
    setError('');
    setLoading(true);
    try {
      await createUserWithEmailAndPassword(auth, email.trim(), password);
      navigate('/dashboard');
    } catch (e) {
      setError(authErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen bg-canvas flex items-center justify-center px-4 overflow-hidden">
      <DoodleAccents variant="auth" />
      <div className="relative w-full max-w-sm">
        <div className="text-center mb-10">
          <h1 className="font-serif text-4xl font-bold text-ink tracking-tight">
            agent<span className="text-brand-500">weave</span>
          </h1>
          <p className="mt-2 text-sm text-muted">Join your AI-powered style companion</p>
        </div>

        <div className="card space-y-4">
          <h2 className="text-lg font-semibold text-ink">Create account</h2>

          {error && (
            <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="input-field"
          />
          <PasswordInput password={password} setPassword={setPassword} onEnter={signup} />

          <button onClick={signup} disabled={loading} className="btn-primary w-full">
            {loading ? 'Creating account…' : 'Create account'}
          </button>
        </div>

        <p className="mt-6 text-center text-sm text-muted">
          Already have an account?{' '}
          <Link to="/login" className="text-brand-600 hover:text-brand-700 transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

export default SignupPage;
