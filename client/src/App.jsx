import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import Loading from './pages/Loading';

const App = () => {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/loading/:uuid" element={<Loading />} />
      </Routes>
    </Router>
  );
};

export default App;
