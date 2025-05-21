import React from 'react';
import ImageForm from '../components/ImageForm';
import Header from '../components/Header';
import Footer from '../components/Footer';
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
    <>
      <Header />
      <main className="container mt-5">
        <ImageForm onSubmit={handleSubmit} />
      </main>
      <Footer />
    </>
  );
};

export default Home;
