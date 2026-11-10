import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { RecordingProvider } from './context/RecordingContext'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RecordingProvider>
      <App />
    </RecordingProvider>
  </React.StrictMode>,
)
