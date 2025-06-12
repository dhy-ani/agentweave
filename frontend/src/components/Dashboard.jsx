import { React, useState } from "react";
import { signOut } from 'firebase/auth';
import { auth, db } from '../firebase';
import { collection, addDoc } from 'firebase/firestore';
import { useNavigate } from 'react-router-dom';
import FashionCard from './FashionCard';
import BodyTypeForm from './BodyTypeForm';

const saveToFirebase = async (recommendation) => {
  try {
    const payload = {
      image: recommendation.image,
      caption: recommendation.result,
      trendiness_score: recommendation.trendiness_score,
      future_projection: recommendation.future_projection,
      timestamp: new Date().toISOString()
    };



    await addDoc(collection(db, "savedOutfits"), payload);
    alert("Outfit saved to Firebase! ");
  } catch (err) {
    console.error("Failed to save:", err);
    alert("Failed to save outfit.");
  }
  
};

const Dashboard = () => {
  const [formData, setFormData] = useState({
    weather: "",
    occasion: "",
    location: "",
    occupation: "",
    gender: ""
  });

  const [results, setResults] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  const [bodyType, setBodyType] = useState(null);
  const [loading, setLoading] = useState(false);
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

      const res = await fetch("http://localhost:8001/stylegenie/trend_vector/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prompt: [
            formData.weather,
            formData.occasion,
            formData.location,
            formData.occupation,
            formData.gender,
            bodyType
          ].join(" ")

        }),
      });
    const data = await res.json();
    setResults(data.results || []);
    setCurrentIndex(0);

   
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
    <div className="dashboard min-h-screen bg-gray-50 py-10 px-6">
      <h1 className="text-4xl font-extrabold text-center text-gray-800 mb-10">StyleGenie Outfit Recommender</h1>

      <div className="bg-white shadow-lg rounded-lg p-6 max-w-2xl mx-auto">
        <BodyTypeForm setBodyType={setBodyType} setLoading={setLoading} />

      {loading && (
        <div className="mt-4">
          <p>Analyzing image...</p>
        </div>
      )}
        {bodyType && (
          <>
            <p className="text-green-600 text-center font-medium mb-4">Detected Body Type: {bodyType}</p>

            <form className="space-y-4 mb-6">
              {Object.keys(formData).map((field) => (
                <input
                  key={field}
                  name={field}
                  placeholder={field.charAt(0).toUpperCase() + field.slice(1)}
                  value={formData[field]}
                  onChange={handleChange}
                  className="w-full p-3 border border-gray-300 rounded-lg shadow-sm"
                  required
                />
              ))}
              <div className="flex justify-between">
                <button
                  onClick={getRecommendation}
                  type="button"
                  className="bg-indigo-600 text-white px-4 py-2 rounded-lg shadow hover:bg-indigo-700"
                >
                  Get Recommendation
                </button>
                {results.length > 1 && currentIndex < results.length - 1 && (
                  <button
                    onClick={() => setCurrentIndex(currentIndex + 1)}
                    className="mt-4 bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
                  >
                    Try Another Look
                  </button>
                )}

                <button
                  onClick={logout}
                  type="button"
                  className="bg-red-600 text-white px-4 py-2 rounded-lg shadow hover:bg-red-700"
                >
                  Log Out
                </button>
              </div>
            </form>
          </>
        )}

      {results.length > 0 && (
        <FashionCard
          image={results[currentIndex].image}
          result={results[currentIndex].result}
          trendiness_score={results[currentIndex].trendiness_score}
          future_projection={results[currentIndex].future_projection}
          onSwipe={(dir) => {
            if (dir === 'up') saveToFirebase(results[currentIndex]);
          }}
        />
      )}

      </div>
    </div>
  );
};

export default Dashboard;
