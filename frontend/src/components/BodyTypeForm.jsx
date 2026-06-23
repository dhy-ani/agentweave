import React, { useState } from 'react';

const API = process.env.REACT_APP_API_URL || 'http://localhost:8001';

const BodyTypeForm = ({ setBodyType, setLoading }) => {
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    setImage(f);
    setPreview(URL.createObjectURL(f));
  };

  const handleUpload = async () => {
    if (!image) { alert('Please select a photo'); return; }
    const fd = new FormData();
    fd.append('file', image);
    try {
      setLoading(true);
      const res = await fetch(`${API}/analyze-body`, { method: 'POST', body: fd });
      const data = await res.json();
      if (data.body_type) {
        setBodyType(data.body_type);
      } else {
        alert(data.error || 'Could not detect body type. Try a clear full-body photo.');
      }
    } catch (err) {
      alert('Upload failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <label className="text-sm font-medium text-neutral-300">
        Step 1 — Upload a full-body photo for body-type analysis
      </label>
      <label
        htmlFor="body-photo"
        className="flex flex-col items-center justify-center border-2 border-dashed border-neutral-700 hover:border-brand-500 rounded-xl py-6 cursor-pointer transition-colors"
      >
        {preview ? (
          <img src={preview} alt="preview" className="h-32 object-contain rounded-lg" />
        ) : (
          <>
            <span className="text-2xl mb-1">🤳</span>
            <span className="text-sm text-neutral-400">Click to upload photo</span>
          </>
        )}
      </label>
      <input id="body-photo" type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
      {image && (
        <button onClick={handleUpload} className="btn-primary w-full">
          Analyze Body Type
        </button>
      )}
    </div>
  );
};

export default BodyTypeForm;
