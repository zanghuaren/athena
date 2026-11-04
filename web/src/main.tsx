import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { loadToken } from './lib/session';
import { initTheme } from './lib/theme';
import './styles/tokens.css';
import './styles/base.css';

initTheme();
await loadToken();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
