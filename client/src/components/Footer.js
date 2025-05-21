import React from 'react';

export default function Footer() {
  return (
    <footer className="bg-primary text-white text-center py-3 mt-5">
      <div className="container">
        <p>{new Date().getFullYear()} - Sistemas Distribuidos - Farres Martin, Yúdica Franco, Suden Paulina </p>
      </div>
    </footer>
  );
}


