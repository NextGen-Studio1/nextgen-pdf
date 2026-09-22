// NextGen PDF — Firebase App, Auth, Firestore, Analytics & Performance Initialization
(function () {
  const config = window.FIREBASE_CONFIG;

  if (!config || !config.apiKey) {
    console.error(
      '[Firebase] Missing FIREBASE_CONFIG. Check js/config.js'
    );
    return;
  }

  const firebaseScript = document.createElement('script');
  firebaseScript.type = 'module';

  firebaseScript.textContent = `
    import { initializeApp } 
      from 'https://www.gstatic.com/firebasejs/10.9.0/firebase-app.js';

    import {
      getAuth,
      setPersistence,
      browserLocalPersistence,
      createUserWithEmailAndPassword,
      signInWithEmailAndPassword,
      signInWithPopup,
      GoogleAuthProvider,
      sendEmailVerification,
      sendPasswordResetEmail,
      signOut,
      updateProfile,
      onAuthStateChanged,
      signInAnonymously,
      linkWithCredential,
      EmailAuthProvider,
      applyActionCode,
      confirmPasswordReset,
      updatePassword,
      reauthenticateWithCredential
    } from 'https://www.gstatic.com/firebasejs/10.9.0/firebase-auth.js';

    import {
      getFirestore,
      doc,
      setDoc,
      getDoc,
      updateDoc,
      serverTimestamp
    } from 'https://www.gstatic.com/firebasejs/10.9.0/firebase-firestore.js';

    import {
      getAnalytics,
      logEvent
    } from 'https://www.gstatic.com/firebasejs/10.9.0/firebase-analytics.js';

    import {
      getPerformance
    } from 'https://www.gstatic.com/firebasejs/10.9.0/firebase-performance.js';

    try {
      // Initialize Firebase App
      const app = initializeApp(window.FIREBASE_CONFIG);

      // Initialize Authentication
      const auth = getAuth(app);

      // Initialize Firestore Database
      const db = getFirestore(app);

      // Initialize Analytics & Performance
      const analytics = getAnalytics(app);
      const perf = getPerformance(app);

      // Expose Firebase services & helpers globally
      window.nextgenFirebase = {
        app,
        auth,
        db,
        analytics,
        perf,
        GoogleAuthProvider,
        createUserWithEmailAndPassword,
        signInWithEmailAndPassword,
        signInWithPopup,
        sendEmailVerification,
        sendPasswordResetEmail,
        signOut,
        updateProfile,
        onAuthStateChanged,
        signInAnonymously,
        linkWithCredential,
        EmailAuthProvider,
        applyActionCode,
        confirmPasswordReset,
        updatePassword,
        reauthenticateWithCredential,
        doc,
        setDoc,
        getDoc,
        updateDoc,
        serverTimestamp
      };

      window.nextgenAnalytics = {
        app,
        analytics,
        perf,
        logEvent: (name, params) => logEvent(analytics, name, params)
      };

      // Set persistence asynchronously without blocking
      setPersistence(auth, browserLocalPersistence).catch((err) => {
        console.warn('[Firebase] Persistence warning:', err);
      });

      console.log('[Firebase] Firebase, Auth, Firestore & Analytics initialized successfully.');

      logEvent(analytics, 'page_view', {
        page_title: document.title,
        page_location: window.location.href
      });

    } catch (error) {
      console.error('[Firebase] Initialization error:', error);
    }
  `;

  document.head.appendChild(firebaseScript);
})();