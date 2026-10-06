import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export const Navbar: React.FC = () => {
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <header className="sticky top-4 z-50 px-4 sm:px-6 lg:px-8 mb-6 sm:mb-8">
      <div className="max-w-[1200px] mx-auto">
        <div className="bg-paper border border-ash rounded-pill px-5 sm:px-6 py-2.5 sm:py-3 flex items-center justify-between shadow-none transition-all">
          
          {/* Logo & Brand */}
          <Link to="/" className="flex items-center space-x-2 group">
            <span className="font-display text-xl sm:text-2xl font-black uppercase tracking-tight text-carbon">
              AUTHENTICA
            </span>
          </Link>

          {/* Navigation Links */}
          <nav className="flex items-center space-x-1 sm:space-x-1.5">
            <Link
              to="/"
              className={`px-3.5 sm:px-4 py-1.5 rounded-pill text-xs font-mono font-bold uppercase transition-all ${
                isActive('/')
                  ? 'bg-carbon text-paper'
                  : 'text-slate hover:text-carbon hover:bg-mist'
              }`}
            >
              Analyze
            </Link>

            <Link
              to="/history"
              className={`px-3.5 sm:px-4 py-1.5 rounded-pill text-xs font-mono font-bold uppercase transition-all ${
                isActive('/history')
                  ? 'bg-carbon text-paper'
                  : 'text-slate hover:text-carbon hover:bg-mist'
              }`}
            >
              History
            </Link>

            <Link
              to="/awareness"
              className={`px-3.5 sm:px-4 py-1.5 rounded-pill text-xs font-mono font-bold uppercase transition-all ${
                isActive('/awareness')
                  ? 'bg-carbon text-paper'
                  : 'text-slate hover:text-carbon hover:bg-mist'
              }`}
            >
              Awareness
            </Link>
          </nav>

        </div>
      </div>
    </header>
  );
};
