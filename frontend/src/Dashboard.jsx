import React, { useState } from "react";
import { signOut } from 'firebase/auth';
import { auth } from './firebase';
import { useNavigate } from 'react-router-dom';

const Dashboard = () => {
  const [formData, setFormData] = useState({
    weather: "",
    occasion: "",
    location: "",
    occupation: "",
    gender: ""
  });

  const [response, setResponse] = useState(null);
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });
  };

  const getRecommendation = async () => {
    try {
      const res = await fetch("http://localhost:8000/stylegenie/trend_vector/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prompt: `${formData.weather} ${formData.occasion} ${formData.location} ${formData.occupation} ${formData.gender}`
        }),
      });

      const data = await res.json();
      setResponse(data);
    } catch (error) {
      alert("Something went wrong: " + error.message);
    }
  };

  const logout = () => {
    signOut(auth)
      .then(() => {
        alert("Logged out successfully!");
        navigate('/login');
      })
      .catch((error) => {
        console.error("Logout error:", error);
      });
  };

  return (
    <div className="dashboard">
      <h1>Get Your StyleGenie Outfit</h1>

      <div className="p-6 max-w-xl mx-auto">
        <h1 className="text-2xl font-bold mb-4">StyleGenie Outfit Recommender</h1>
        <form className="space-y-4">
          {Object.keys(formData).map((field) => (
            <input
              key={field}
              name={field}
              placeholder={field.charAt(0).toUpperCase() + field.slice(1)}
              value={formData[field]}
              onChange={handleChange}
              className="w-full p-2 border rounded"
              required={field !== "relevance"}
            />
          ))}
          <button onClick={getRecommendation} type="button" className="bg-blue-600 text-white px-4 py-2 rounded">
            Get Recommendation
          </button>
          <button onClick={logout} type="button" className="bg-red-600 text-white px-4 py-2 rounded ml-2">
            Log Out
          </button>
        </form>

        {response && (
          <div className="mt-6 p-4 border rounded bg-gray-50">
            <h2 className="text-xl font-semibold">StyleGenie says:</h2>
            <p><strong>Outfit:</strong> {response.result}</p>
            <p><strong>Trendiness Score:</strong> {response.trendiness_score}</p>
            <p><strong>Future Outlook:</strong> {response.future_projection}</p>
            <img src={response.image} alt="Recommended Look" className="mt-4 w-full rounded" />
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
