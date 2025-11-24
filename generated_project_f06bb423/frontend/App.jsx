const { useState, useEffect } = React;

const API_BASE_URL = 'http://localhost:8001';

function App() {
  const [image, setImage] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [currentImageId, setCurrentImageId] = useState(null);
  const [brightness, setBrightness] = useState(50);
  const [filter, setFilter] = useState('none');
  const [guides, setGuides] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [imageData, setImageData] = useState(null);

  const handleImageChange = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    
    setImageFile(file);
    setImage(URL.createObjectURL(file));
    setError(null);
    setSuccess(null);
    
    // Upload image to backend
    await uploadImage(file);
  };

  const uploadImage = async (file) => {
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await fetch(`${API_BASE_URL}/images/upload`, {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errorData.detail || `Upload failed: ${response.statusText}`);
      }
      
      const data = await response.json();
      setCurrentImageId(data.id);
      setImageData(data);
      setSuccess('Image uploaded successfully!');
    } catch (err) {
      setError(err.message);
      console.error('Upload error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleBrightnessChange = (event) => {
    setBrightness(parseInt(event.target.value));
  };

  const handleFilterChange = (event) => {
    setFilter(event.target.value);
  };

  const handleGuidesChange = (event) => {
    setGuides(event.target.checked);
  };

  const resizeImage = async () => {
    if (!currentImageId) {
      setError('Please upload an image first');
      return;
    }
    
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/images/${currentImageId}/resize?width=800&height=600`,
        { method: 'POST' }
      );
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errorData.detail || `Resize failed: ${response.statusText}`);
      }
      
      const data = await response.json();
      setImageData(data);
      setSuccess('Image resized successfully!');
    } catch (err) {
      setError(err.message);
      console.error('Resize error:', err);
    } finally {
      setLoading(false);
    }
  };

  const adjustBrightness = async () => {
    if (!currentImageId) {
      setError('Please upload an image first');
      return;
    }
    
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/images/${currentImageId}/brightness?brightness=${brightness}`,
        { method: 'POST' }
      );
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errorData.detail || `Brightness adjustment failed: ${response.statusText}`);
      }
      
      const data = await response.json();
      setImageData(data);
      setSuccess(`Brightness adjusted to ${brightness}%!`);
    } catch (err) {
      setError(err.message);
      console.error('Brightness error:', err);
    } finally {
      setLoading(false);
    }
  };

  const applyFilter = async () => {
    if (!currentImageId) {
      setError('Please upload an image first');
      return;
    }
    
    if (filter === 'none') {
      setError('Please select a filter');
      return;
    }
    
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/images/${currentImageId}/filter?filter=${filter}`,
        { method: 'POST' }
      );
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errorData.detail || `Filter application failed: ${response.statusText}`);
      }
      
      const data = await response.json();
      setImageData(data);
      setSuccess(`Filter "${filter}" applied successfully!`);
    } catch (err) {
      setError(err.message);
      console.error('Filter error:', err);
    } finally {
      setLoading(false);
    }
  };

  const saveImage = async () => {
    if (!currentImageId) {
      setError('Please upload an image first');
      return;
    }
    
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/images/${currentImageId}/save`,
        { method: 'POST' }
      );
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errorData.detail || `Save failed: ${response.statusText}`);
      }
      
      const data = await response.json();
      setSuccess('Image saved successfully!');
    } catch (err) {
      setError(err.message);
      console.error('Save error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Load guided tour on mount
  useEffect(() => {
    const loadGuidedTour = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/guided-tour`);
        if (response.ok) {
          const data = await response.json();
          console.log('Guided tour:', data);
        }
      } catch (err) {
        console.error('Failed to load guided tour:', err);
      }
    };
    loadGuidedTour();
  }, []);

  return (
    <div className="max-w-4xl mx-auto p-4">
      <h1 className="text-3xl font-bold mb-4">Image Processing Tool</h1>
      
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          <strong>Error:</strong> {error}
        </div>
      )}
      {success && (
        <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4">
          <strong>Success:</strong> {success}
        </div>
      )}
      
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">Upload Image:</label>
        <input 
          type="file" 
          accept="image/*"
          onChange={handleImageChange}
          className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          disabled={loading}
        />
      </div>
      
      {image && (
        <div className="mb-4">
          <img 
            src={image} 
            alt="Processed Image" 
            className="w-full h-64 object-cover rounded border-2 border-gray-300"
          />
          {imageData && (
            <div className="mt-2 text-sm text-gray-600">
              <p>Image ID: {imageData.id}</p>
              <p>Size: {imageData.width} x {imageData.height}</p>
              {imageData.brightness !== undefined && <p>Brightness: {imageData.brightness}%</p>}
              {imageData.filter && <p>Filter: {imageData.filter}</p>}
            </div>
          )}
        </div>
      )}
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">
            Brightness: {brightness}%
          </label>
          <input
            type="range"
            min="0"
            max="100"
            value={brightness}
            onChange={handleBrightnessChange}
            className="w-full"
            disabled={loading || !currentImageId}
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium mb-2">Filter:</label>
          <select
            value={filter}
            onChange={handleFilterChange}
            className="w-full p-2 border border-gray-300 rounded"
            disabled={loading || !currentImageId}
          >
            <option value="none">None</option>
            <option value="grayscale">Grayscale</option>
            <option value="sepia">Sepia</option>
            <option value="blur">Blur</option>
            <option value="sharpen">Sharpen</option>
          </select>
        </div>
        
        <div>
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={guides}
              onChange={handleGuidesChange}
              className="mr-2"
              disabled={loading}
            />
            <span>Show Guides</span>
          </label>
        </div>
      </div>
      
      <div className="mt-6 flex flex-wrap gap-2">
        <button 
          onClick={resizeImage} 
          disabled={loading || !currentImageId}
          className="bg-blue-500 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-bold py-2 px-4 rounded"
        >
          {loading ? 'Processing...' : 'Resize Image'}
        </button>
        <button 
          onClick={adjustBrightness} 
          disabled={loading || !currentImageId}
          className="bg-blue-500 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-bold py-2 px-4 rounded"
        >
          {loading ? 'Processing...' : 'Adjust Brightness'}
        </button>
        <button 
          onClick={applyFilter} 
          disabled={loading || !currentImageId || filter === 'none'}
          className="bg-blue-500 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-bold py-2 px-4 rounded"
        >
          {loading ? 'Processing...' : 'Apply Filter'}
        </button>
        <button 
          onClick={saveImage} 
          disabled={loading || !currentImageId}
          className="bg-green-500 hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-bold py-2 px-4 rounded"
        >
          {loading ? 'Saving...' : 'Save Image'}
        </button>
      </div>
      
      {loading && (
        <div className="mt-4 text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          <p className="mt-2 text-gray-600">Processing...</p>
        </div>
      )}
    </div>
  );
}
