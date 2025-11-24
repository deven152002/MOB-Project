import React, { useState, useEffect } from 'react';
import TailwindComponents from 'tailwind-components-react';

const App = () => {
  const [codeExplaination, setCodeExplanation] = useState('');
  const [quizGeneration, setQuizGeneration] = useState(false);
  const [progressTracking, setProgressTracking] = useState(0);

  useEffect(() => {
    fetch('https://api.github.com/user')
      .then(response => response.json())
      .then(data => console.log(data));
  }, []);

  const handleCodeExplanation = () => {
    // API call to get code explanation
    fetch('/code-explanation')
      .then(response => response.json())
      .then(data => setCodeExplanation(data));
  };

  const handleQuizGeneration = () => {
    // API call to generate quiz
    fetch('/quiz-generation')
      .then(response => response.json())
      .then(data => setQuizGeneration(data));
  };

  const handleProgressTracking = () => {
    // API call to track progress
    fetch('/progress-tracking')
      .then(response => response.json())
      .then(data => setProgressTracking(data));
  };

  return (
    <TailwindComponents>
      <div className="max-w-4xl mx-auto p-4">
        <h1 className="text-3xl font-bold mb-2">Python Programming Exercises</h1>
        <button
          className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
          onClick={handleCodeExplanation}
        >
          Code Explanation
        </button>
        <button
          className="bg-orange-500 hover:bg-orange-700 text-white font-bold py-2 px-4 rounded"
          onClick={handleQuizGeneration}
        >
          Quiz Generation
        </button>
        <button
          className="bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded"
          onClick={handleProgressTracking}
        >
          Progress Tracking
        </button>
      </div>

      {quizGeneration && (
        <div className="max-w-4xl mx-auto p-4">
          <h1 className="text-3xl font-bold mb-2">Quiz Generation</h1>
          <p>Answer the following questions to complete the exercise:</p>
          <ul>
            <li>Question 1: {codeExplaination}</li>
            <li>Question 2: (to be generated)</li>
            <li>Question 3: (to be generated)</li>
          </ul>
        </div>
      )}

      {progressTracking && (
        <div className="max-w-4xl mx-auto p-4">
          <h1 className="text-3xl font-bold mb-2">Progress Tracking</h1>
          <p>Track your progress and earn rewards!</p>
          <p>Completed exercises: {progressTracking}</p>
        </div>
      )}
    </TailwindComponents>
  );
};

export default App;