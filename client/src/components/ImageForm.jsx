import React, { useState } from 'react';
import { fetchRenderedImage } from '../services/imageService';

const defaultParams = {
  width: 800,
  height: 600,
  block_size: 4,
  samples: 100,
  camerax: 0,
  cameray: 0,
  zoom: 1,
  type: 0,
};

const ImageForm = ({ setImageSrc }) => {
  const [params, setParams] = useState(defaultParams);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  // Dentro de handleSubmit en ImageForm.jsx
  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const { data } = await fetchRenderedImage(params);

      const jobUuid = data.uuid;
      // Poll para la imagen, hasta que esté disponible
      const interval = setInterval(async () => {
        try {
          const res = await fetch(`http://${window.location.hostname}:30081/image/${jobUuid}`);
          if (res.status === 200) {
            const blob = await res.blob();
            const imgUrl = URL.createObjectURL(blob);
            setImageSrc(imgUrl);
            clearInterval(interval);
          }
        } catch (err) {
          // Ignorar error 404 para seguir esperando
        }
      }, 1000);

    } catch (err) {
      console.error(err);
      alert('Error al contactar el servidor.');
    }
  };



  return (
    <form onSubmit={handleSubmit} className="row g-3">
      {Object.entries(params).map(([key, value]) => (
        <div className="col-md-6" key={key}>
          <label htmlFor={key} className="form-label">
            {key}
          </label>
          <input
            type={'number'}
            className="form-control"
            id={key}
            name={key}
            value={value}
            onChange={handleChange}
          />
        </div>
      ))}

      <div className="col-12">
        <button type="submit" className="btn btn-primary w-100">
          Generar Imagen
        </button>
      </div>
    </form>
  );
};

export default ImageForm;
