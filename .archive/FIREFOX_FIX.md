# Firefox "Error loading dashboard" Fix

## Issue
Firefox users are seeing "Error loading dashboard" because they have an old JWT token stored in localStorage that was created before we fixed the token format.

## Root Cause
The old tokens had `sub` (subject) as an integer instead of a string, which causes a 422 error: "Subject must be a string".

## Solution

### For Users (Immediate Fix)
1. **Clear localStorage in Firefox:**
   - Open Firefox DevTools (F12)
   - Go to Storage tab → Local Storage
   - Delete `access_token` and `user` entries
   - Refresh the page and log in again

2. **Or simply log out and log back in:**
   - Click on your user profile in the sidebar
   - Log out (if logout button exists)
   - Log back in with your credentials

### Automatic Fix (Implemented)
The application now automatically detects old token format errors (422 status) and:
- Clears the invalid token from localStorage
- Redirects to the login page
- Shows a helpful error message

## Technical Details

### What Changed
1. **Dashboard Error Handling:** Improved error messages that detect 422 errors and suggest re-login
2. **API Interceptor:** Added automatic detection and cleanup of old token format errors
3. **Token Format:** All new tokens are created with `sub` as a string (e.g., `"9"` instead of `9`)

### How to Verify
1. Check browser console for errors
2. Check Network tab - look for 422 responses to `/api/dashboard`
3. Verify token format:
   ```javascript
   // In browser console
   const token = localStorage.getItem('access_token');
   const payload = JSON.parse(atob(token.split('.')[1]));
   console.log('Token sub:', payload.sub, 'Type:', typeof payload.sub);
   // Should show: Token sub: "9" Type: string
   ```

## Prevention
All new registrations and logins will automatically get the correct token format. The issue only affects users who logged in before the fix was deployed.
