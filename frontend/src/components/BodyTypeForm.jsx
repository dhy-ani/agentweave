import React, { useState } from 'react';

const BodyTypeForm = ({ setBodyType, setLoading }) => {
  const [image, setImage] = useState(null);

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected) {
      setImage(selected);
    }
  };

  const handleUpload = async () => {
  console.log("🖼 Upload button clicked");

  if (!image) {
    alert("Please select an image");
    return;
  }

  const formData = new FormData();
  formData.append("file", image);

  try {
    setLoading(true);
    console.log("📡 Sending image to backend...");

    const res = await fetch("http://localhost:8001/analyze-body", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();
    console.log("✅ Server responded:", data);

    if (data.body_type) {
      setBodyType(data.body_type);
    } else {
      alert(data.error || "Unknown error");
    }

  } catch (err) {
    console.error("❌ Upload failed:", err);
    alert("Upload failed: " + err.message);
  } finally {
    setLoading(false);
  }
    

};



  return (
    <div className="mb-4">
      <input
        type="file"
        accept="image/*"
        onChange={handleFileChange}
        className="border p-2"
      />
      <button
        onClick={handleUpload}
        className="ml-2 bg-blue-600 text-white px-4 py-2 rounded"
      >
        Analyze Body Type
      </button>
    </div>
  );
};

export default BodyTypeForm;
