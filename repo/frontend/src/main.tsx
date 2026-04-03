import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// Minimal stub — expanded fully in Phase 4
function App() {
  return (
    <div style={{ color: '#fff', background: '#0f172a', minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'system-ui' }}>
      <div style={{ textAlign: 'center' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Warehouse Intelligence Platform</h1>
        <p style={{ color: '#94a3b8' }}>Backend bootstrapping — Phase 1.4 in progress</p>
      </div>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
