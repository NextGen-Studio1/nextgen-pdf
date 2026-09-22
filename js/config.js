// Smart API Base URL detection:
// On localhost (127.0.0.1 / localhost): calls local FastAPI server http://127.0.0.1:8000/api/v1
// On production hosting (e.g. nextgen-pdf.web.app): routes to /api/v1
const isLocalhost = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';
window.NEXTGEN_API_BASE = window.NEXTGEN_API_BASE || (
  isLocalhost
    ? 'http://127.0.0.1:8000/api/v1'
    : 'https://nextgen-pdf-api.onrender.com/api/v1'
);

// Firebase Console & Analytics Configuration
window.FIREBASE_CONFIG = window.FIREBASE_CONFIG || {
  apiKey: "AIzaSyDG93Jo2e3HxpKRR5dNc4gptpiKJ1mh6gk",
  authDomain: "nextgen-pdf.firebaseapp.com",
  projectId: "nextgen-pdf",
  storageBucket: "nextgen-pdf.firebasestorage.app",
  messagingSenderId: "848017304912",
  appId: "1:848017304912:web:9e7da087b57a7a383e5055",
  measurementId: "G-EJXBBVD5L9"
};

// Google AdSense & Monetization Configuration
window.ADSENSE_CONFIG = window.ADSENSE_CONFIG || {
  enabled: true,
  publisherId: "ca-pub-5453249687281273",
  testMode: false
};
