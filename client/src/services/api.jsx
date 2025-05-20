import axios from 'axios';

const API_URL = `http://${window.location.hostname}:30080/api`;

export const submitJob = async (params) => {
  const response = await axios.put(`${API_URL}/submit-job`, params);
  return response.data.uuid;
};

export const getImage = async (uuid) => {
  try {
    const response = await axios.get(`${API_URL}/get-image/${uuid}`, {
      responseType: 'blob', // Esto indica que esperamos un blob o imagen binaria
      validateStatus: (status) => (status >= 200 && status < 300) || status === 202 || status === 404,
    });

    if (response.status === 200) {
      // Imagen lista, retornamos el blob directamente
      return response.data;
    } else if (response.status === 202) {
      // Imagen todavía procesándose
      return null;
    } else if (response.status === 404) {
      throw new Error('UUID not found');
    }
  } catch (error) {
    // Aquí puede haber un error de red o error 500 etc.
    throw error;
  }
};

