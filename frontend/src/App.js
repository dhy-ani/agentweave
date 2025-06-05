
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import LoginPage from './LoginPage';
import SignupPage from './SignupPage';
import Dashboard from './Dashboard';




function App() {
  const isLoggedin = localStorage.getItem("authToken");
  return (
    <BrowserRouter>


      <Routes>
        {isLoggedin ?(
          <Route path="/*" element ={<Dashboard />} />
        ): (
        <>

        <Route path="/signup" element={<SignupPage />} />
        <Route path="/" element={<LoginPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={<Dashboard />} />

        </>
        )}
      </Routes>
    </BrowserRouter>
  );
}

export default App;
