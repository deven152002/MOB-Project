// Configuration for API endpoints
export const API_BASE_URL = 'http://localhost:8000';

export const apiCall = async (endpoint, method = 'GET', data = null) => {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };

  if (data) {
    options.body = JSON.stringify(data);
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
  if (!response.ok) {
    throw new Error(`API call failed: ${response.statusText}`);
  }
  return await response.json();
};
