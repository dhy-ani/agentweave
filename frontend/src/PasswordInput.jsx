import { useState } from "react";
import { FaEye, FaEyeSlash } from "react-icons/fa";



function PasswordInput({ password, setPassword }) {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <input
        type={showPassword ? "text" : "password"}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
        style={{ paddingRight: "20px" }}
      />
      <span
        onClick={() => setShowPassword(!showPassword)}
        style={{
          position: "absolute",
          right: "8px",
          top: "50%",
          transform: "translateY(-50%)",
          cursor: "pointer",
        }}
      >
        {showPassword ? <FaEyeSlash /> : <FaEye />}
      </span>
    </div>
  );
}

export default PasswordInput;