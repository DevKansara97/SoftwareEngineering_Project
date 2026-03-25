# Google Authentication Setup Guide

## Overview
This guide explains how to set up Google OAuth 2.0 authentication for Seva Connect.

## Prerequisites
- Google Cloud Console account
- OAuth 2.0 credentials already created in Google Cloud Console
- API key and redirect URIs already configured

## Step 1: Install Dependencies

Update your Python dependencies:
```bash
cd backend
pip install -r ../requirements.txt
```

New packages added:
- `python-dotenv` - For loading environment variables from `.env`
- `google-auth` - Google authentication library
- `google-auth-oauthlib` - OAuth library for Google
- `google-auth-httplib2` - HTTP library for Google auth
- `requests` - For making HTTP requests to Google APIs

## Step 2: Configure Environment Variables

Update the `.env` file in the project root with your Google credentials:

```env
GOOGLE_CLIENT_ID=your_actual_client_id_here
GOOGLE_CLIENT_SECRET=your_actual_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:5000/auth/google/callback
```

### For Production:
Change `GOOGLE_REDIRECT_URI` to your production domain:
```env
GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/google/callback
```

## Step 3: Update Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Go to **Credentials**
4. Find your OAuth 2.0 Client ID
5. Click **Edit**
6. Under **Authorized redirect URIs**, add:
   - For development: `http://localhost:5000/auth/google/callback`
   - For production: `https://yourdomain.com/auth/google/callback`
7. Click **Save**

## How It Works

### Frontend Flow:
1. User clicks "Sign with Google" button on login page
2. Frontend calls `POST /api/auth/google/init` to get Google's authorization URL
3. Frontend redirects user to Google login/permission screen
4. User authorizes the app
5. Google redirects to `/auth/google/callback?code=...&state=...`
6. Callback page processes the code and calls `GET /api/auth/google/callback` API
7. API exchanges code for access token and retrieves user info
8. User is created or found in the database
9. User data is stored in localStorage and user is redirected to dashboard

### Backend Flow:
1. **POST /api/auth/google/init**: Generates Google OAuth URL with CSRF protection (state token)
2. **GET /api/auth/google/callback**: 
   - Receives authorization code from Google
   - Exchanges code for access token
   - Retrieves user info from Google
   - Creates user if doesn't exist (defaults to DONOR role)
   - Returns user data as JSON

## API Endpoints

### Initiate Google OAuth
```
POST /api/auth/google/init

Response:
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "message": "Redirect user to this URL for Google login"
}
```

### Google OAuth Callback (API)
```
GET /api/auth/google/callback?code=...&state=...

Response on success:
{
  "message": "Google login successful!",
  "user_id": 123,
  "name": "John Doe",
  "email": "john@example.com",
  "role": "DONOR"
}

Response on error:
{
  "error": "Error message describing what went wrong"
}
```

## New User Behavior

When a user logs in with Google for the first time:
- A new user account is created automatically
- Default role is set to **DONOR** (can be changed manually in database)
- Phone number is set to placeholder "9999999999" (should be updated by user)
- A donor profile is created with basic information

## Security Features

1. **CSRF Protection**: State token is generated and validated
2. **Environment Variables**: Credentials are stored in `.env` and NOT committed to git
3. **Token Exchange**: Authentication code is exchanged server-side (not exposed to frontend)
4. **Session Management**: User session is created after successful authentication
5. **Password-less**: OAuth users don't need to maintain passwords

## Troubleshooting

### "GOOGLE_CLIENT_ID not configured in .env"
- Make sure `.env` file exists in project root
- Check that `GOOGLE_CLIENT_ID` is set with actual value from GCP
- Restart Flask server after updating `.env`

### Redirect URI mismatch error
- Verify the `GOOGLE_REDIRECT_URI` in `.env` matches exactly what's in Google Cloud Console
- Check for HTTP vs HTTPS mismatch
- Check for trailing slashes or port number differences

### "Invalid state parameter - possible CSRF attack"
- This is a security feature
- Usually means the session was lost or state parameter was tampered with
- Try logging in again

### OAuth initialized but redirect doesn't work
- Check browser console for errors
- Verify `.env` file has valid credentials
- Make sure Flask server is running

## Files Modified/Created

- `.env` - New environment configuration file (credentials stored here)
- `requirements.txt` - Updated with new dependencies
- `backend/app.py` - Updated to load `.env` and add callback page route
- `backend/routes/auth.py` - Added Google OAuth endpoints and helper functions
- `frontend/templates/login.html` - Updated with Google Sign-In button
- `frontend/templates/google_callback.html` - New callback processor page

## Next Steps

1. Install dependencies: `pip install -r requirements.txt`
2. Update `.env` with your Google credentials
3. Update Google Cloud Console with your redirect URI
4. Restart Flask development server
5. Test Google login on the login page

## Notes

- `.env` file should NOT be committed to git (add to `.gitignore` if not already)
- Environment variables are only loaded during server startup
- Changing credentials in `.env` requires restarting the server
- OAuth sessions are stored in Flask session (requires session management)
