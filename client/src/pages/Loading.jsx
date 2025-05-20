import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Button, Container, Spinner, Row, Col } from 'react-bootstrap';
import { getImage } from '../services/api';

export default function Loading() {
  const { uuid } = useParams();
  const navigate = useNavigate();
  const [imageSrc, setImageSrc] = useState(null);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(null);

  useEffect(() => {
    // Recuperar parámetros enviados desde localStorage
    const saved = localStorage.getItem('last_job_params');
    if (saved) setParams(JSON.parse(saved));
  }, []);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const blob = await getImage(uuid);
        if (blob) {
          setImageSrc(URL.createObjectURL(blob));
          clearInterval(interval);
        }
      } catch {
        setError('Error al procesar la imagen.');
        clearInterval(interval);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [uuid]);

  const renderDescription = () => {
    if (!params) return null;
    return (
      <Card.Text className="mt-4 text-start">
        <h5>Parámetros:</h5>
        <ul>
          {Object.entries(params).map(([key, value]) => (
            <li key={key}>
              <strong>{key}:</strong> {value}
            </li>
          ))}
        </ul>
      </Card.Text>
    );
  };

  return (
    <Container className="my-5 d-flex justify-content-center">
      <Card style={{ maxWidth: '600px', width: '100%' }}>
        <Card.Body className="text-center">
          {!imageSrc && !error ? (
            <>
              <Spinner animation="border" role="status" />
              <h4 className="mt-3">Generando tu fractal...</h4>
              <Button variant="link" className="mt-3" onClick={() => navigate('/')}>Volver al inicio</Button>
            </>
          ) : error ? (
            <>
              <h4 className="text-danger">{error}</h4>
              <div className="mt-3">
                <Button variant="secondary" onClick={() => window.location.reload()}>Intentar de nuevo</Button>{' '}
                <Button variant="link" onClick={() => navigate('/')}>Volver al inicio</Button>
              </div>
            </>
          ) : (
            <>
              <Card.Img variant="top" src={imageSrc} alt="Fractal generado" />
              {renderDescription()}
              <Button variant="link" className="mt-3" onClick={() => navigate('/')}>Volver al inicio</Button>
            </>
          )}
        </Card.Body>
      </Card>
    </Container>
  );
}
