import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { submitJob } from '../services/api';

const DEFAULT_PARAMS = {
  width: 800,
  height: 600,
  block_size: 4,
  samples: 100,
  camerax: 0,
  cameray: 0,
  zoom: 1,
  type: 0,
  color_mode: 0,
};

export default function ImageForm() {
  const navigate = useNavigate();
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    try {
      const saved = localStorage.getItem('last_job_params');
      if (saved) setParams(JSON.parse(saved));
    } catch {}
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    // Convert to number (int or float)
    const numeric = name.includes('julia') || name === 'zoom' || name === 'camerax' || name === 'cameray'
      ? parseFloat(value)
      : parseInt(value, 10);
    setParams(prev => ({
      ...prev,
      [name]: numeric
    }));
  };

  const handleTypeChange = (e) => {
    setParams(prev => ({ ...prev, type: Number(e.target.value) }));
  };

  const handleColorModeChange = (e) => {
    setParams(prev => ({ ...prev, color_mode: Number(e.target.value) }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      localStorage.setItem('last_job_params', JSON.stringify(params));
      const uuid = await submitJob(params);
      navigate(`/loading/${uuid}`);
    } catch (err) {
      console.error(err);
      setError('Error al enviar los parámetros.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container my-5">
      <div className="card shadow mx-auto" style={{ maxWidth: '600px' }}>
        <div className="card-body">
          <h4 className="card-title text-center mb-4">Elegir características</h4>
          <form onSubmit={handleSubmit}>
            <div className="row g-3">
              {Object.entries(params)
                .filter(([key]) => key !== 'type' && key !== 'color_mode')
                .map(([key, val]) => (
                  <div className="col-md-6" key={key}>
                    <label htmlFor={key} className="form-label text-capitalize">
                      {key.replace(/_/g, ' ')}
                    </label>
                    <input
                      type="number"
                      step={key.includes('julia') || ['zoom', 'camerax', 'cameray'].includes(key) ? 'any' : '1'}
                      className="form-control"
                      id={key}
                      name={key}
                      value={val}
                      onChange={handleChange}
                      required
                    />
                  </div>
                ))}

              <div className="col-md-12">
                <label htmlFor="type" className="form-label">Tipo de Fractal</label>
                <select
                  id="type"
                  className="form-select"
                  value={params.type}
                  onChange={handleTypeChange}
                >
                  <option value="0">Mandelbrot</option>
                  <option value="1">Julia Set</option>
                </select>
              </div>

              <div className="col-md-12">
                <label htmlFor="color_mode" className="form-label">Modo de Color</label>
                <select
                  id="color_mode"
                  className="form-select"
                  value={params.color_mode}
                  onChange={handleColorModeChange}
                >
                  <option value="0">Black & White</option>
                  <option value="1">Grayscale</option>
                  <option value="2">Blue Green Red</option>
                </select>
              </div>

              {error && (
                <div className="col-12">
                  <div className="alert alert-danger py-2" role="alert">
                    {error}
                  </div>
                </div>
              )}

              <div className="col-12">
                <button
                  type="submit"
                  className="btn btn-primary w-100"
                  disabled={loading}
                >
                  {loading ? 'Generando...' : 'Generar Imagen'}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
