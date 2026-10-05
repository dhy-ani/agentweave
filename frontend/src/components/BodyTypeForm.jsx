import React, { useState } from "react";
import { CameraIcon } from "./icons";
import { API } from "../config";
import { resizeImage } from "../lib/resizeImage";

const BodyTypeForm = ({ setBodyType, setLoading }) => {
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    setError("");
    setImage(f);
    setPreview(URL.createObjectURL(f));
  };

  const handleUpload = async () => {
    if (!image) return;
    setError("");
    try {
      setLoading(true);
      const fd = new FormData();
      fd.append("file", await resizeImage(image));
      const res = await fetch(`${API}/analyze-body`, { method: "POST", body: fd });
      const data = await res.json();
      if (data.body_type && data.body_type !== "unknown") {
        setBodyType(data.body_type);
      } else {
        setError(data.error || data.detail || "We couldn't see a full body. Try a clear, front-facing full-length photo.");
      }
    } catch (err) {
      setError("Upload failed. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <label htmlFor="body-photo"
        className="flex flex-col items-center justify-center border-2 border-dashed border-line-strong hover:border-brand-500 rounded-xl py-8 cursor-pointer transition-colors">
        {preview ? (
          <img src={preview} alt="Selected full-body" className="h-40 object-contain rounded-lg" />
        ) : (
          <>
            <CameraIcon className="w-7 h-7 mb-2 text-muted" />
            <span className="text-sm text-muted">Click to upload a full-body photo</span>
          </>
        )}
      </label>
      <input id="body-photo" type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {image && (
        <button onClick={handleUpload} className="btn-primary w-full">
          Analyze body shape
        </button>
      )}
    </div>
  );
};

export default BodyTypeForm;
