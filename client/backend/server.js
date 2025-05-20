const express = require('express');
const bodyParser = require('body-parser');
const fs = require('fs');

const app = express();
const port = 30081; // Asegúrate que sea accesible por el servidor principal

// Aceptar buffers PNG directamente
app.use(bodyParser.raw({ type: 'image/png', limit: '10mb' }));

// En memoria temporal
const imageCache = new Map();

app.post('/callback', (req, res) => {
  const uuid = req.headers['x-job-uuid'];
  if (!uuid) {
    return res.status(400).send('Missing UUID');
  }

  console.log(`Imagen recibida para UUID: ${uuid}`);
  imageCache.set(uuid, req.body);  // Guarda el buffer
  res.sendStatus(200);
});

app.get('/image/:uuid', (req, res) => {
  const uuid = req.params.uuid;
  const image = imageCache.get(uuid);
  if (!image) {
    return res.status(404).send('Imagen no encontrada');
  }
  res.set('Content-Type', 'image/png');
  res.send(image);
});

app.listen(port, () => {
  console.log(`Client backend listening on port ${port}`);
});
