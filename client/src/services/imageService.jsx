import axios from 'axios';

const API_URL =`http://${window.location.hostname}:30080`;

export const fetchRenderedImage = async (params) => {
  const payload = {
    ...params,
    callback_url: `${window.location.origin}/callback`
  };

  try {
    const { data } = await axios.put(
      `${API_URL}/api/submit-job`,
      payload,
      { headers: { "Content-Type": "application/json" } }
    );
    console.log("Job UUID:", data.uuid);
  } catch (err) {
    console.error("Submit job error:", err.response?.data || err.message);
  }
}
