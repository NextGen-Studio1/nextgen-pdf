// Smart API Base URL detection:
// On localhost (127.0.0.1 / localhost): calls local FastAPI server http://127.0.0.1:8000/api
// On production hosting (e.g. nextgen-pdf.web.app): routes to /api
const isLocalhost = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';
window.NEXTGEN_API_BASE = window.NEXTGEN_API_BASE || (
  isLocalhost
    ? 'http://127.0.0.1:8000/api'
    : 'https://nextgen-pdf-api.onrender.com/api'
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
  publisherId: "", // Replace with your ca-pub-XXXXXXXXXXXXXXXX ID when ready
  testMode: true   // Shows visual placeholder banner slots until real publisher ID is set
};
