import React, { useState, useEffect } from 'react';
import './index.css';
import TailwindExpo from '@expo/tailwindcss';

function App() {
  const [description, setDescription] = useState('');
  const [examples, setExamples] = useState([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    fetch('https://api.example.com/chatbot')
      .then(response => response.json())
      .then(data => {
        setDescription(data.description);
        setExamples(data.examples);
      })
      .catch(error => console.error(error));
  }, []);

  const handleConnect = () => {
    // Connect to GitLab CI/CD pipelines
    console.log('Connected to GitLab CI/CD pipelines');
    setConnected(true);
  };

  return (
    <div className="max-w-4xl mx-auto p-4">
      <h1 className="text-3xl font-bold mb-2">Chatbot Description</h1>
      {description && (
        <p className="text-lg">{description}</p>
      )}
      <button
        className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
        onClick={handleConnect}
      >
        Connect to GitLab CI/CD pipelines
      </button>
      {connected && (
        <div className="mt-4">
          <h2 className="text-2xl font-bold mb-2">Examples</h2>
          <ul>
            {examples.map(example => (
              <li key={example.id} className="mb-2">
                <code>{example.code}</code>
                <p>{example.description}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Example() {
  return (
    <div className="bg-white p-4 rounded mb-4">
      <h3 className="text-lg font-bold mb-2">{example.name}</h3>
      <code>{example.code}</code>
      <p>{example.description}</p>
    </div>
  );
}

function CodeEditor() {
  return (
    <div className="w-full h-screen p-4 bg-gray-100">
      <textarea
        className="w-full h-full p-2 resize-none"
        placeholder="Write your code here..."
      />
    </div>
  );
}

function ChatbotDescription() {
  return (
    <div className="max-w-4xl mx-auto p-4">
      <h1 className="text-3xl font-bold mb-2">Chatbot Description</h1>
      <CodeEditor />
      <button
        className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
        onClick={() => console.log('Code explanation')}
      >
        Code Explanation
      </button>
    </div>
  );
}

function Examples() {
  return (
    <div className="max-w-4xl mx-auto p-4">
      <h1 className="text-3xl font-bold mb-2">Examples</h1>
      <ul>
        {examples.map(example => (
          <li key={example.id} className="mb-2">
            <Example example={example} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function Integration() {
  return (
    <div className="max-w-4xl mx-auto p-4">
      <h1 className="text-3xl font-bold mb-2">Integration</h1>
      <button
        className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
        onClick={() => console.log('Integration with development tools')}
      >
        Integration with Development Tools
      </button>
    </div>
  );
}

function AppContainer() {
  return (
    <TailwindExpo>
      <App />
      <ChatbotDescription />
      <Examples />
      <Integration />
    </TailwindExpo>
  );
}

export default AppContainer;