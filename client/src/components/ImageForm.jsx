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

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const imageUrl = await fetchRenderedImage(params);
      setImageSrc(imageUrl);
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
