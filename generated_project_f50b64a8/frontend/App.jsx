import React, { useState, useEffect } from 'react';
import './index.css';

function ChatWindow() {
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [username, setUsername] = useState('Your Name');

  useEffect(() => {
    // API call to fetch messages
    const fetchMessages = async () => {
      const response = await fetch('/api/messages');
      const data = await response.json();
      setMessages(data);
    };
    fetchMessages();
  }, []);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    // API call to send message
    const sendMessage = async () => {
      const response = await fetch('/api/sendMessage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: newMessage }),
      });
      const data = await response.json();
      setMessages([...messages, data]);
      setNewMessage('');
    };
    sendMessage();
  };

  return (
    <div className="chat-window">
      <header>
        <h1>Chat with Us</h1>
      </header>
      <main>
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.type}`}>
            <p>{username}: {message.text}</p>
          </div>
        ))}
        <form onSubmit={handleSendMessage}>
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Type a message..."
          />
          <button type="submit">Send</button>
        </form>
      </main>
    </div>
  );
}

function Header() {
  return (
    <header className="header">
      <h1>Virtual Assistant</h1>
    </header>
  );
}

function Footer() {
  return (
    <footer className="footer">
      <p>&copy; 2023 Your Company</p>
    </footer>
  );
}

function App() {
  return (
    <div className="app">
      <Header />
      <ChatWindow />
      <Footer />
    </div>
  );
}

export default App;