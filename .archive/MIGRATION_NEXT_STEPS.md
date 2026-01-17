# React Migration - Next Steps to Make It Work

## Overview
The React frontend has been created and the Flask backend has been converted to a REST API. Here are the steps to get everything working.

## Step 1: Build the React Frontend

The frontend needs to be built before Flask can serve it:

```bash
cd frontend
npm install  # If not already done
npm run build
```

This creates the `frontend/dist/` directory that Flask serves.

## Step 2: Verify Environment Variables

Ensure your `.env` file has:

```bash
FLASK_SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here  # Can be same as FLASK_SECRET_KEY
```

## Step 3: Test the Backend API

Start the Flask backend:

```bash
cd campaign_ui
python app.py
```

Or use Docker Compose:

```bash
docker-compose up campaign-ui
```

Test the API endpoints:

```bash
# Test registration
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"test123","password_confirm":"test123"}'

# Test login (save the token)
TOKEN=$(curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"test123"}' \
  | jq -r '.access_token')

# Test protected endpoint
curl http://localhost:5000/api/dashboard \
  -H "Authorization: Bearer $TOKEN"
```

## Step 4: Test the Frontend (Development Mode)

In a separate terminal:

```bash
cd frontend
npm run dev
```

The frontend will run on `http://localhost:5173` and proxy API requests to `http://localhost:5000`.

**Test the frontend:**
1. Open `http://localhost:5173`
2. Register a new user or login
3. Navigate through the pages:
   - Dashboard
   - Campaigns (list, create, edit)
   - Jobs (list, details)
   - Documents
   - Account

## Step 5: Test Production Build (Flask Serving React)

1. Build the React app:
   ```bash
   cd frontend
   npm run build
   ```

2. Start Flask:
   ```bash
   cd campaign_ui
   python app.py
   ```

3. Open `http://localhost:5000` in your browser
   - The Flask backend should serve the React app
   - All routes should work (client-side routing)
   - API calls should go to `/api/*`

## Step 6: Test with Docker

Build and run the full stack:

```bash
docker-compose build campaign-ui
docker-compose up campaign-ui
```

The Dockerfile includes a multi-stage build that:
1. Builds the React app
2. Copies it into the Python container
3. Flask serves it

## Common Issues and Fixes

### Issue: "React app is not built yet" error
**Fix:** Run `npm run build` in the `frontend` directory

### Issue: CORS errors in browser console
**Fix:** Ensure Flask CORS is configured correctly (already done in `app.py`)

### Issue: 401 Unauthorized errors
**Fix:** 
- Check that JWT token is being stored in localStorage
- Verify `JWT_SECRET_KEY` is set in environment
- Check that the Authorization header is being sent: `Bearer <token>`

### Issue: API endpoints return 404
**Fix:** 
- Verify the route exists in `campaign_ui/app.py`
- Check that the route uses `@jwt_required()` not `@login_required`
- Ensure the route path matches what the frontend expects

### Issue: Static assets (CSS/JS) not loading
**Fix:**
- Verify `frontend/dist/assets/` directory exists after build
- Check that Flask routes `/assets/*` and `/vite.svg` are working
- Check browser console for 404 errors on specific assets

### Issue: Page shows "Loading..." forever
**Fix:**
- Check browser console for errors
- Verify API endpoints are returning data
- Check network tab to see if requests are failing
- Verify React Query is handling errors correctly

## Missing Features to Implement

The following features from the old Flask templates may need additional work:

1. **File Upload/Download** - Document upload endpoints exist but may need frontend integration
2. **Cover Letter Generation** - API exists but frontend may need UI
3. **Job Notes** - May need frontend UI for CRUD operations
4. **Campaign Status Polling** - May need React polling implementation
5. **DAG Triggering** - May need frontend button/UI

## Testing Checklist

- [ ] User registration works
- [ ] User login works
- [ ] JWT token is stored and sent with requests
- [ ] Dashboard loads and shows stats
- [ ] Campaigns list loads
- [ ] Campaign create/edit works
- [ ] Jobs list loads
- [ ] Job details page loads
- [ ] Documents page loads
- [ ] Account page loads
- [ ] Password change works
- [ ] Logout works
- [ ] Protected routes redirect to login
- [ ] Static assets (CSS/JS) load correctly
- [ ] Client-side routing works (no 404s on refresh)

## Next Development Steps

1. **Add Error Handling**: Improve error messages and loading states
2. **Add Form Validation**: Client-side validation for all forms
3. **Add File Upload UI**: Implement drag-and-drop or file picker
4. **Add Toast Notifications**: Replace alerts with toast notifications
5. **Add Loading Skeletons**: Better loading states
6. **Add Error Boundaries**: Catch React errors gracefully
7. **Add Unit Tests**: Test React components
8. **Add E2E Tests**: Test full user flows

## Production Deployment

Before deploying to production:

1. Set strong `FLASK_SECRET_KEY` and `JWT_SECRET_KEY`
2. Configure CORS origins for production domain
3. Set up HTTPS
4. Configure proper error logging
5. Set up monitoring/alerting
6. Test all features thoroughly
7. Remove or secure old Flask template routes if not needed
