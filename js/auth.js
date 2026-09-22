/* NextGen PDF — Central Authentication & User Management Service */

(function () {
  const NextGenAuth = {
    // Utility: Wait for Firebase SDK initialization
    waitForFirebase() {
      return new Promise((resolve) => {
        if (window.nextgenFirebase && window.nextgenFirebase.auth) {
          return resolve(window.nextgenFirebase);
        }
        const check = setInterval(() => {
          if (window.nextgenFirebase && window.nextgenFirebase.auth) {
            clearInterval(check);
            resolve(window.nextgenFirebase);
          }
        }, 50);
      });
    },

    // Get current logged in user
    getCurrentUser() {
      return window.nextgenFirebase?.auth?.currentUser || null;
    },

    // Monitor authentication state changes
    onAuthChange(callback) {
      this.waitForFirebase().then(({ auth, onAuthStateChanged }) => {
        onAuthStateChanged(auth, callback);
      });
    },

    // Sync / create user profile document in Firestore
    async syncUserProfile(user, extraData = {}) {
      try {
        const { db, doc, getDoc, setDoc, serverTimestamp } = await this.waitForFirebase();
        if (!user || user.isAnonymous || !db) return null;

        const userRef = doc(db, 'users', user.uid);
        const userSnap = await getDoc(userRef);

        if (!userSnap.exists()) {
          const profileData = {
            uid: user.uid,
            name: user.displayName || extraData.fullName || 'User',
            email: user.email || '',
            photoURL: user.photoURL || '',
            plan: 'free',
            role: 'user',
            status: 'active',
            createdAt: serverTimestamp(),
            lastLoginAt: serverTimestamp(),
            emailVerified: user.emailVerified,
            ...extraData
          };
          await setDoc(userRef, profileData);
          return profileData;
        } else {
          const existingData = userSnap.data();
          const updateData = {
            lastLoginAt: serverTimestamp(),
            emailVerified: user.emailVerified,
            name: user.displayName || existingData.name
          };
          await setDoc(userRef, updateData, { merge: true });
          return { ...existingData, ...updateData };
        }
      } catch (err) {
        // Non-blocking warning: Firestore may be unavailable
        console.debug('[NextGenAuth] Firestore sync profile skipped:', err?.message || err);
        return null;
      }
    },

    // Get user profile from Firestore (non-blocking fallback)
    async getUserProfile(uid) {
      try {
        const { db, doc, getDoc } = await this.waitForFirebase();
        if (!uid || !db) return null;
        const userRef = doc(db, 'users', uid);
        const userSnap = await getDoc(userRef);
        return userSnap.exists() ? userSnap.data() : null;
      } catch (err) {
        // Non-blocking silent fallback to Auth user details if Firestore is disabled/offline
        console.debug('[NextGenAuth] Firestore profile read skipped:', err?.message || err);
        return null;
      }
    },

    // Register with Email & Password
    async register({ email, password, fullName }) {
      const { auth, createUserWithEmailAndPassword, updateProfile, sendEmailVerification } = await this.waitForFirebase();
      
      const credential = await createUserWithEmailAndPassword(auth, email, password);
      const user = credential.user;

      if (fullName) {
        await updateProfile(user, { displayName: fullName });
      }

      // Sync Firestore profile
      await this.syncUserProfile(user, { fullName });

      // Send verification email
      try {
        await sendEmailVerification(user);
      } catch (e) {
        console.warn('[NextGenAuth] Verification email trigger warning:', e);
      }

      return user;
    },

    // Login with Email & Password
    async login({ email, password }) {
      const { auth, signInWithEmailAndPassword } = await this.waitForFirebase();
      const credential = await signInWithEmailAndPassword(auth, email, password);
      const user = credential.user;

      // Sync Firestore last login
      await this.syncUserProfile(user);

      return user;
    },

    // Sign in / Sign up with Google Popup
    async googleLogin() {
      const { auth, signInWithPopup, GoogleAuthProvider } = await this.waitForFirebase();
      const provider = new GoogleAuthProvider();
      const credential = await signInWithPopup(auth, provider);
      const user = credential.user;

      // Sync Firestore profile
      await this.syncUserProfile(user);

      return user;
    },

    // Anonymous Guest Login for visitors using PDF tools
    async initAnonymousGuest() {
      const { auth, signInAnonymously } = await this.waitForFirebase();
      if (!auth.currentUser) {
        try {
          const cred = await signInAnonymously(auth);
          console.log('[NextGenAuth] Anonymous guest session active:', cred.user.uid);
          return cred.user;
        } catch (e) {
          console.warn('[NextGenAuth] Anonymous auth failed:', e);
        }
      }
      return auth.currentUser;
    },

    // Send email verification
    async sendVerificationEmail() {
      const { auth, sendEmailVerification } = await this.waitForFirebase();
      if (!auth.currentUser) throw new Error('No user logged in.');
      await sendEmailVerification(auth.currentUser);
    },

    // Send password reset email
    async sendPasswordReset(email) {
      const { auth, sendPasswordResetEmail } = await this.waitForFirebase();
      await sendPasswordResetEmail(auth, email);
    },

    // Confirm password reset with action code
    async confirmPasswordResetCode(oobCode, newPassword) {
      const { auth, confirmPasswordReset } = await this.waitForFirebase();
      await confirmPasswordReset(auth, oobCode, newPassword);
    },

    // Update user password for currently signed in user
    async updateUserPassword(newPassword) {
      const { auth, updatePassword } = await this.waitForFirebase();
      if (!auth.currentUser) throw new Error('No user logged in.');
      await updatePassword(auth.currentUser, newPassword);
    },

    // Sign out user
    async logout() {
      const { auth, signOut } = await this.waitForFirebase();
      await signOut(auth);
      window.location.href = '/pages/auth/login.html';
    },

    // Protect dashboard routes (Require authentication guard)
    async requireAuth(redirectUrl = '/pages/auth/login.html') {
      const { auth, onAuthStateChanged } = await this.waitForFirebase();
      
      return new Promise((resolve) => {
        onAuthStateChanged(auth, async (user) => {
          if (!user || user.isAnonymous) {
            console.warn('[NextGenAuth] Unauthorized access attempt, redirecting to login...');
            window.location.href = redirectUrl;
          } else {
            // Populate UI elements on dashboard if present
            this.updateDashboardUI(user);
            resolve(user);
          }
        });
      });
    },

    // Helper: Update user UI elements in sidebar/header if present
    async updateDashboardUI(user) {
      const profile = await this.getUserProfile(user.uid);
      const userEmail = user.email || '';
      const displayName = user.displayName || profile?.name || (userEmail ? userEmail.split('@')[0] : 'User');
      const initial = displayName.charAt(0).toUpperCase();

      document.querySelectorAll('[data-user-name]').forEach(el => {
        el.textContent = displayName;
      });

      document.querySelectorAll('[data-user-greeting]').forEach(el => {
        el.textContent = `Welcome back, ${displayName} 👋`;
      });

      document.querySelectorAll('[data-user-avatar-initial]').forEach(el => {
        el.textContent = initial;
      });

      document.querySelectorAll('[data-user-email]').forEach(el => {
        el.textContent = userEmail;
      });

      document.querySelectorAll('[data-user-plan]').forEach(el => {
        el.textContent = (profile?.plan || 'Free').toUpperCase();
      });

      document.querySelectorAll('[data-user-avatar]').forEach(el => {
        if (user.photoURL) {
          el.src = user.photoURL;
        }
      });
    }
  };

  window.NextGenAuth = NextGenAuth;
})();
