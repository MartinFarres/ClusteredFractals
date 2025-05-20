import React from 'react';
import ImageForm from '../components/ImageForm';
import { useNavigate } from 'react-router-dom';
import { submitJob } from '../services/api';

const Home = () => {
  const navigate = useNavigate();

  const handleSubmit = async (params) => {
    try {
      const uuid = await submitJob(params);
      navigate(`/loading/${uuid}`);
    } catch (err) {
      alert('Error al enviar el trabajo.');
      console.error(err);
    }
  };

  return (
    <div className="container mt-5">
      <h2 className="mb-4">Generar Fractal</h2>
      <ImageForm onSubmit={handleSubmit} />
    </div>
  );
};

export default Home;
