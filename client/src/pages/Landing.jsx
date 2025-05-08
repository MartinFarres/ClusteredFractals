import React, { useState } from 'react';
import ImageForm from '../components/ImageForm';

const Landing = () => {
  const [imageSrc, setImageSrc] = useState(null);

  return (
    <div className="container mt-5">
      <h1 className="mb-4 text-center">Fractal Image Generator</h1>
      <ImageForm setImageSrc={setImageSrc} />

      {imageSrc && (
        <div className="mt-5 text-center">
          <h2>Resultado:</h2>
          <img src={imageSrc} alt="Render" className="img-fluid border" />
        </div>
      )}
    </div>
  );
};

export default Landing;
