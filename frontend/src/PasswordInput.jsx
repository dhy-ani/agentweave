import { useState } from 'react';

function PasswordInput({ password, setPassword, onEnter }) {
  const [show, setShow] = useState(false);

  return (
    <div className="relative">
      <input
        type={show ? 'text' : 'password'}
        placeholder="Password"
        value={password}
        onChange={e => setPassword(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && onEnter?.()}
        className="input-field pr-14"
      />
      <button
        type="button"
        onClick={() => setShow(s => !s)}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink text-xs transition-colors"
      >
        {show ? 'Hide' : 'Show'}
      </button>
    </div>
  );
}

export default PasswordInput;