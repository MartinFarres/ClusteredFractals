import axios from 'axios';

const SERVER_IP = process.env.REACT_APP_SERVER_IP;


export const fetchRenderedImage = async (params) => {
  const response = await axios.post(`${SERVER_IP}/api/submit-job`, params, {
    responseType: 'blob', // Esperamos una imagen binaria
  });
  return URL.createObjectURL(response.data);
};
