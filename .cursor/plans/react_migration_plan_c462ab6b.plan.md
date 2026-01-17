---
name: React Migration Plan
overview: Migrate the Flask-based campaign UI to a React SPA with Vite, converting Flask to a pure REST API backend with JWT authentication.
todos:
  - id: backend_install_jwt_deps
    content: Install JWT and CORS dependencies - update requirements.txt with flask-jwt-extended and flask-cors
    status: completed
  - id: backend_jwt_config
    content: Add JWT and CORS configuration to Flask app - initialize JWTManager and CORS
    status: completed
    dependencies:
      - backend_install_jwt_deps
  - id: backend_auth_endpoints
    content: Create auth API endpoints - POST /api/auth/login and POST /api/auth/register returning JWT tokens
    status: completed
    dependencies:
      - backend_jwt_config
  - id: backend_jwt_decorator
    content: Add JWT authentication decorator - replace @login_required with JWT middleware
    status: completed
    dependencies:
      - backend_auth_endpoints
  - id: backend_dashboard_api
    content: Convert dashboard route to API endpoint - GET /api/dashboard returns JSON stats
    status: completed
    dependencies:
      - backend_jwt_decorator
  - id: backend_campaigns_list_api
    content: Convert campaigns list to API endpoint - GET /api/campaigns returns JSON list
    status: completed
    dependencies:
      - backend_jwt_decorator
  - id: backend_campaigns_crud_api
    content: Convert campaign CRUD routes to API endpoints - GET/POST/PUT/DELETE /api/campaigns/:id
    status: completed
    dependencies:
      - backend_campaigns_list_api
  - id: backend_jobs_api
    content: Convert job routes to API endpoints - GET /api/jobs, GET /api/jobs/:id, POST /api/jobs/:id/status
    status: completed
    dependencies:
      - backend_jwt_decorator
  - id: backend_remaining_routes_api
    content: Convert remaining routes to API endpoints - documents, account, user endpoints
    status: completed
    dependencies:
      - backend_jobs_api
  - id: backend_react_serve
    content: Add route to serve React SPA - catch-all route for non-API routes
    status: completed
    dependencies:
      - backend_remaining_routes_api
  - id: frontend_init_vite
    content: Initialize React + Vite project - create frontend directory, install dependencies
    status: completed
  - id: frontend_project_structure
    content: Set up project structure - create directories, migrate CSS assets
    status: completed
    dependencies:
      - frontend_init_vite
  - id: frontend_api_client
    content: Create API client service - Axios instance with JWT token handling and interceptors
    status: completed
    dependencies:
      - frontend_project_structure
  - id: frontend_auth_context
    content: Create AuthContext provider - user state, login/logout functions, JWT token storage
    status: completed
    dependencies:
      - frontend_api_client
  - id: frontend_router_setup
    content: Set up React Router - configure routes, add authentication guards, 404 page
    status: completed
    dependencies:
      - frontend_project_structure
  - id: frontend_layout_components
    content: Create Layout and Sidebar components - migrate from templates
    status: completed
    dependencies:
      - frontend_router_setup
  - id: frontend_login_page
    content: Create Login page - migrate form, integrate with AuthContext, add validation
    status: completed
    dependencies:
      - frontend_auth_context
      - frontend_layout_components
  - id: frontend_register_page
    content: Create Register page - migrate form, integrate with API, add validation
    status: completed
    dependencies:
      - frontend_auth_context
      - frontend_layout_components
  - id: frontend_dashboard_page
    content: Create Dashboard page - migrate from template, use React Query for stats
    status: completed
    dependencies:
      - frontend_api_client
      - frontend_layout_components
  - id: frontend_campaigns_list_page
    content: Create Campaigns list page - fetch and display campaigns using React Query
    status: completed
    dependencies:
      - frontend_api_client
      - frontend_layout_components
  - id: frontend_campaign_details_page
    content: Create Campaign Details page - fetch data, implement status polling, DAG trigger
    status: completed
    dependencies:
      - frontend_campaigns_list_page
  - id: frontend_campaign_create_edit_pages
    content: Create Campaign Create and Edit pages - migrate forms, add validation, React Query mutations
    status: completed
    dependencies:
      - frontend_campaign_details_page
  - id: frontend_jobs_list_page
    content: Create Jobs list page - fetch jobs, implement filtering and sorting
    status: completed
    dependencies:
      - frontend_api_client
      - frontend_layout_components
  - id: frontend_job_details_page
    content: Create Job Details page - fetch job data, status updates, notes CRUD
    status: completed
    dependencies:
      - frontend_jobs_list_page
  - id: frontend_documents_page
    content: Create Documents page - file upload, resume/cover letter lists, deletion
    status: completed
    dependencies:
      - frontend_api_client
      - frontend_layout_components
  - id: frontend_account_page
    content: Create Account Management page - user profile, password change form
    status: completed
    dependencies:
      - frontend_api_client
      - frontend_layout_components
  - id: frontend_shared_components
    content: Create shared UI components - modals, forms, badges, loading states, error display
    status: completed
    dependencies:
      - frontend_project_structure
  - id: frontend_vite_proxy
    content: Configure Vite proxy - forward /api/* requests to Flask backend
    status: completed
    dependencies:
      - frontend_api_client
  - id: infra_dockerfile_update
    content: Update Dockerfile for React build - multi-stage build with Node.js and Python
    status: completed
    dependencies:
      - backend_react_serve
      - frontend_init_vite
  - id: infra_docker_compose_update
    content: Update docker-compose.yml - ensure environment variables and service configuration
    status: completed
    dependencies:
      - infra_dockerfile_update
  - id: cleanup_old_files
    content: Remove old template and JavaScript files - delete templates/ and static/js/ directories
    status: completed
    dependencies:
      - frontend_campaign_create_edit_pages
      - frontend_job_details_page
      - frontend_documents_page
      - frontend_account_page
  - id: cleanup_docs
    content: Update requirements.txt and README - document React setup and dependencies
    status: completed
    dependencies:
      - cleanup_old_files
---

# React SPA Migration Plan

## Overview

Migrate the Flask-based campaign UI (`campaign_ui/`) to a React Single Page Application (SPA) using Vite. Convert Flask backend to a pure REST API that returns JSON. Replace Flask-Login (session-based) with JWT authentication.

## Architecture

### Current State

- **Backend**: Flask app with Jinja2 templates, Flask-Login (session-based auth), 40+ routes mixing `render_template()` and `jsonify()`
- **Frontend**: Jinja2 templates + vanilla JavaScript (multiple `.js` files)
- **Deployment**: Single Docker container serving both backend and templates

### Target State

- **Backend**: Flask REST API (JSON responses only), JWT authentication, CORS enabled
- **Frontend**: React SPA built with Vite, React Router, React Query (TanStack Query), Axios
- **Deployment**: Separate build process (React build served by Flask or nginx), or separate containers

## Implementation Steps

### Phase 1: Backend API Migration

#### 1.1 Authentication: Flask-Login → JWT

- **File**: `campaign_ui/app.py`
- Install `flask-jwt-extended` or `PyJWT`
- Add JWT configuration (secret key, expiration)
- Create `/api/auth/login` and `/api/auth/register` endpoints returning JWT tokens
- Add JWT authentication decorator/middleware (replacing `@login_required`)
- Remove Flask-Login dependencies

#### 1.2 Convert Routes to API Endpoints

- **File**: `campaign_ui/app.py`
- Convert all `render_template()` routes to `jsonify()` responses:
  - **Dashboard**: `GET /api/dashboard` → returns stats JSON
  - **Campaigns**: 
    - `GET /api/campaigns` → list campaigns
    - `GET /api/campaigns/:id` → campaign details
    - `POST /api/campaigns` → create campaign
    - `PUT /api/campaigns/:id` → update campaign
    - `DELETE /api/campaigns/:id` → delete campaign
    - `POST /api/campaigns/:id/toggle-active` → toggle active status
    - `GET /api/campaigns/:id/status` → campaign status (already JSON)
  - **Jobs**:
    - `GET /api/jobs?campaign_id=:id` → list jobs
    - `GET /api/jobs/:job_id` → job details
    - `POST /api/jobs/:job_id/status` → update job status
    - Job notes endpoints (already JSON)
  - **Documents**: Resume/cover letter endpoints (mostly already JSON)
  - **User**: `GET /api/user/profile`, `PUT /api/user/password`
- Standardize error responses: `{"error": "message"}` with appropriate HTTP status codes

#### 1.3 Add CORS Middleware

- Install `flask-cors`
- Configure CORS to allow requests from React dev server (localhost:5173) and production domain
- Add CORS headers to all API responses

#### 1.4 Serve React Build (Production)

- Add route to serve React `index.html` for all non-API routes (catch-all)
- Configure Flask to serve static files from React build directory
- Update Dockerfile to include React build step or serve via nginx

### Phase 2: Frontend Setup

#### 2.1 Initialize React + Vite Project

- Create new directory structure within `campaign_ui/`:
  ```
  campaign_ui/
    ├── frontend/           # React app
    │   ├── src/
    │   ├── public/
    │   ├── package.json
    │   └── vite.config.js
    ├── app.py             # Flask API (modified)
    └── ...
  ```

- Initialize Vite React project: `npm create vite@latest frontend -- --template react`
- Install dependencies:
  - `react-router-dom` (routing)
  - `@tanstack/react-query` (server state management)
  - `axios` (API client)
  - `js-cookie` or `react-cookie` (JWT token storage)

#### 2.2 Project Structure

- **Components**: `src/components/` (shared components)
- **Pages**: `src/pages/` (route components)
- **Hooks**: `src/hooks/` (custom hooks)
- **Services**: `src/services/` (API client, auth service)
- **Context**: `src/context/` (Auth context)
- **Utils**: `src/utils/` (helpers, formatters)
- **Assets**: `src/assets/` (CSS, images - migrate existing CSS)

#### 2.3 API Client Setup

- **File**: `frontend/src/services/api.js`
- Create Axios instance with base URL and interceptors
- Add JWT token to request headers (from cookie/localStorage)
- Handle 401 responses (redirect to login)
- Export API functions for each endpoint group (campaigns, jobs, auth, etc.)

#### 2.4 Authentication Context

- **File**: `frontend/src/context/AuthContext.jsx`
- Create Auth context/provider for user state
- Implement login/logout functions
- Store JWT token in localStorage or httpOnly cookie
- Protect routes with authentication check

### Phase 3: Component Migration

#### 3.1 Core Layout Components

- **Base Layout**: `src/components/Layout.jsx` (replaces `templates/base.html`)
- **Sidebar**: `src/components/Sidebar.jsx` (from `templates/components/sidebar.html`)
- **Navigation**: React Router `Link` components
- Migrate CSS: Move existing CSS files to `src/assets/css/` and import in main entry

#### 3.2 Authentication Pages

- **Login**: `src/pages/Login.jsx` (from `templates/login.html`)
- **Register**: `src/pages/Register.jsx` (from `templates/register.html`)
- Use React Query mutations for login/register
- Handle form validation and error display

#### 3.3 Dashboard Page

- **File**: `src/pages/Dashboard.jsx`
- Replace `templates/dashboard.html`
- Use React Query to fetch dashboard stats
- Display cards/stats using existing CSS classes

#### 3.4 Campaign Pages

- **List**: `src/pages/Campaigns.jsx` (from `templates/list_campaigns.html`)
- **View**: `src/pages/CampaignDetails.jsx` (from `templates/view_campaign.html`)
- **Create**: `src/pages/CreateCampaign.jsx` (from `templates/create_campaign.html`)
- **Edit**: `src/pages/EditCampaign.jsx` (from `templates/edit_campaign.html`)
- Migrate form logic from `static/js/addCampaign.js`
- Use React Query for data fetching and mutations
- Status polling: Use React Query's `refetchInterval` or custom polling hook

#### 3.5 Job Pages

- **List**: `src/pages/Jobs.jsx` (from `templates/jobs.html`)
- **Details**: `src/pages/JobDetails.jsx` (from `templates/job_details.html`)
- Migrate filtering/sorting logic from `static/js/jobDetails.js`
- Status update modal/dropdown
- Notes management (CRUD)

#### 3.6 Documents Page

- **File**: `src/pages/Documents.jsx` (from `templates/documents.html`)
- File upload components
- Resume/cover letter lists
- Migrate upload logic from `static/js/documents.js`

#### 3.7 Account Management

- **File**: `src/pages/AccountManagement.jsx` (from `templates/account_management.html`)
- Password change form

#### 3.8 Shared Components

- **Modals**: Ranking modal, delete confirmation, status modals
- **Forms**: Reusable form components (input, select, checkbox groups)
- **Status Badges**: Job status, campaign status badges
- **Loading States**: Spinners, skeleton loaders
- **Error Display**: Error messages, toast notifications

### Phase 4: JavaScript Logic Migration

#### 4.1 Replace Vanilla JS with React Patterns

- **Form Validation**: React Hook Form or custom validation hooks
- **Status Polling**: React Query `refetchInterval` or `usePolling` hook
- **Modal Management**: React state instead of DOM manipulation
- **Table Sorting**: React state + sorting functions
- **Debouncing**: React hooks (useDebounce)
- **Local Storage**: React hooks (useLocalStorage)

#### 4.2 Migrate Complex Logic

- **Campaign Status Polling**: `static/js/campaignDetails.js` → React Query polling
- **DAG Triggering**: API mutation in React Query
- **File Uploads**: React file input + FormData API calls
- **Real-time Updates**: React Query refetch on intervals or WebSocket (future)

### Phase 5: Routing Setup

#### 5.1 React Router Configuration

- **File**: `frontend/src/App.jsx`
- Define routes matching existing Flask routes:
  - `/login`, `/register`
  - `/dashboard`
  - `/campaigns`, `/campaigns/:id`, `/campaigns/:id/edit`, `/campaigns/create`
  - `/jobs`, `/jobs/:campaign_id`, `/jobs/details/:job_id`
  - `/documents`
  - `/account`
- Add route guards (require authentication)
- Add 404 page

### Phase 6: Build & Deployment

#### 6.1 Development Setup

- **Vite Dev Server**: Runs on `localhost:5173` (or configured port)
- **Flask API**: Runs on `localhost:5000`
- Configure Vite proxy to forward API requests to Flask

#### 6.2 Production Build

- Update `campaign_ui/Dockerfile`:
  - Multi-stage build: Node.js stage for React build, Python stage for Flask
  - Build React app: `npm run build`
  - Copy build output to Flask static directory
  - Serve via Flask or nginx
- Alternative: Separate containers (React served by nginx, Flask API)

#### 6.3 Update docker-compose.yml

- Update `campaign-ui` service to use new Dockerfile
- Ensure environment variables are passed correctly
- Test build and deployment

### Phase 7: Testing & Cleanup

#### 7.1 Remove Old Files

- Delete `templates/` directory
- Delete `static/js/` directory (logic migrated to React)
- Keep `static/css/` temporarily for reference (migrated to `frontend/src/assets/css/`)

#### 7.2 Update Dependencies

- Update `campaign_ui/requirements.txt`:
  - Add `flask-jwt-extended`, `flask-cors`
  - Remove `flask-login` (if no longer needed)
- Add `campaign_ui/frontend/package.json` with React dependencies

#### 7.3 Documentation

- Update README with React dev setup instructions
- Document API endpoints (consider OpenAPI/Swagger)
- Update deployment documentation

## Key Files to Create/Modify

### Backend

- `campaign_ui/app.py` - Convert to pure API, add JWT auth, CORS
- `campaign_ui/requirements.txt` - Add JWT and CORS packages

### Frontend

- `campaign_ui/frontend/` - New React app directory
- `campaign_ui/frontend/package.json` - React dependencies
- `campaign_ui/frontend/vite.config.js` - Vite configuration
- `campaign_ui/frontend/src/main.jsx` - React entry point
- `campaign_ui/frontend/src/App.jsx` - Router setup
- `campaign_ui/frontend/src/services/api.js` - API client
- `campaign_ui/frontend/src/context/AuthContext.jsx` - Auth context
- `campaign_ui/frontend/src/pages/*.jsx` - Page components
- `campaign_ui/frontend/src/components/*.jsx` - Shared components

### Infrastructure

- `campaign_ui/Dockerfile` - Multi-stage build for React + Flask
- `docker-compose.yml` - Update campaign-ui service if needed

## Migration Order (Recommended)

1. **Phase 1** (Backend API) - Foundation for frontend
2. **Phase 2** (Frontend Setup) - Get React app running
3. **Phase 3.1-3.2** (Layout + Auth) - Basic navigation
4. **Phase 3.3** (Dashboard) - Simple page to test API integration
5. **Phase 3.4** (Campaigns) - Core feature
6. **Phase 3.5-3.7** (Jobs, Documents, Account) - Remaining features
7. **Phase 4-7** (Polish, Build, Cleanup)

## Step-by-Step Implementation Workflow

### Implementation Process

Each implementation step must follow this workflow:

1. **Implement Changes** - Make code changes according to the step requirements
2. **Run Linting** - Verify code quality (`ruff check` for Python, ESLint for JavaScript/React)
3. **Run Tests** - Execute unit/integration tests if applicable
4. **Manual Testing** - Test functionality manually
5. **Browser Testing** - Use browser tools to verify UI/UX (when applicable)
6. **Verify Backward Compatibility** - Ensure existing functionality still works
7. **Commit** - Commit with clear message describing the step
8. **Push & Verify CI** - Push to remote and verify CI passes

### Commit Strategy

Each implementation step must be committed separately with descriptive commit messages following the format:

```
[TYPE]: Brief description

- Detailed change 1
- Detailed change 2
- Verification steps performed
```

Types:

- `backend:` - Backend API changes
- `frontend:` - Frontend React changes
- `infra:` - Docker, docker-compose, build configuration
- `chore:` - Dependencies, configuration, documentation

Example:

```
backend: Add JWT authentication endpoints

- Install flask-jwt-extended
- Create /api/auth/login endpoint returning JWT token
- Create /api/auth/register endpoint
- Add JWT middleware decorator
- Verified: Login/register returns JWT tokens, tokens work for protected routes
```

### Verification Tools & Processes

#### 1. Code Quality Verification

**Python (Backend)**:

- Run `ruff check campaign_ui/` - Must pass with no errors
- Run `ruff format --check campaign_ui/` - Verify formatting
- Run `pytest tests/unit/` - Run unit tests if applicable

**JavaScript/React (Frontend)**:

- Run `npm run lint` (if configured) - ESLint check
- Run `npm run build` - Verify build succeeds without errors
- Type checking (if TypeScript enabled)

#### 2. API Endpoint Verification

For each API endpoint:

- **Manual Testing**: Use `curl` or Postman/Insomnia to test endpoints
- **Test Cases**:
  - Valid requests return expected JSON responses
  - Invalid requests return appropriate error codes (400, 401, 403, 404, 500)
  - Authentication required endpoints reject unauthenticated requests
  - JWT tokens are validated correctly
- **Response Validation**: Verify response structure matches expected schema

Example verification script:

```bash
# Test login endpoint
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}' \
  | jq

# Test protected endpoint with JWT
curl -X GET http://localhost:5000/api/campaigns \
  -H "Authorization: Bearer $JWT_TOKEN" \
  | jq
```

#### 3. Browser Testing (UI Verification)

For frontend components and pages, use browser tools to verify:

**Browser Testing Checklist**:

- [ ] Page loads without console errors
- [ ] UI elements render correctly (layout, colors, fonts)
- [ ] Forms submit correctly and show validation errors
- [ ] Navigation works (routes change, back/forward buttons)
- [ ] Interactive elements work (buttons, modals, dropdowns)
- [ ] Loading states display during API calls
- [ ] Error messages display appropriately
- [ ] Responsive design works (test mobile/tablet/desktop views)
- [ ] Authentication flow works (login/logout redirects correctly)

**Browser Testing Process**:

1. Start Flask API: `python campaign_ui/app.py` (or `docker-compose up campaign-ui`)
2. Start React dev server: `cd campaign_ui/frontend && npm run dev`
3. Navigate to `http://localhost:5173` in browser
4. Open browser DevTools (F12):

   - **Console**: Check for JavaScript errors, warnings
   - **Network**: Verify API requests succeed, check request/response payloads
   - **Application**: Verify localStorage/cookies store tokens correctly

5. Test each feature manually:

   - Click through navigation
   - Fill out forms
   - Trigger API calls
   - Test error scenarios (invalid inputs, network errors)

**Using Browser MCP Tools**:

- Use `mcp_cursor-browser-extension_browser_navigate` to navigate to pages
- Use `mcp_cursor-browser-extension_browser_snapshot` to capture page state
- Use `mcp_cursor-browser-extension_browser_click` to interact with elements
- Use `mcp_cursor-browser-extension_browser_fill_form` to test forms
- Use `mcp_cursor-browser-extension_browser_console_messages` to check for errors
- Use `mcp_cursor-browser-extension_browser_network_requests` to verify API calls

#### 4. Integration Testing

For steps that integrate frontend and backend:

- **End-to-End Flow**: Test complete user flows (e.g., login → view campaigns → create campaign)
- **API Integration**: Verify React components successfully call Flask API endpoints
- **Authentication Flow**: Test JWT token storage, refresh, and expiration
- **Error Handling**: Verify error scenarios (network failures, invalid responses) are handled gracefully

#### 5. CI Verification

After each commit and push:

- Wait for CI pipeline to complete
- Verify all CI jobs pass:
  - `lint-and-format` - Linting passes
  - `test` - Unit/integration tests pass
  - `dbt-test` - Database tests pass (if applicable)
- If CI fails, fix issues before proceeding to next step

### Step-by-Step Implementation Plan

Each step below represents a single commit:

#### Step 1: Backend - Install JWT Dependencies

- **Files**: `campaign_ui/requirements.txt`
- **Changes**: Add `flask-jwt-extended`, `flask-cors`
- **Verification**:
  - Run `pip install -r campaign_ui/requirements.txt`
  - Verify imports work: `python -c "from flask_jwt_extended import JWTManager; from flask_cors import CORS; print('OK')"`
- **Commit**: `chore: Add JWT and CORS dependencies for API migration`

#### Step 2: Backend - Add JWT Configuration

- **Files**: `campaign_ui/app.py`
- **Changes**: 
  - Import JWT and CORS
  - Initialize JWT and CORS
  - Configure JWT secret key and expiration
- **Verification**:
  - Run `python campaign_ui/app.py` - Server starts without errors
  - Check Flask logs for JWT initialization messages
- **Commit**: `backend: Add JWT and CORS configuration`

#### Step 3: Backend - Create Auth API Endpoints

- **Files**: `campaign_ui/app.py`
- **Changes**: 
  - Create `POST /api/auth/login` endpoint
  - Create `POST /api/auth/register` endpoint
  - Return JWT tokens in responses
- **Verification**:
  - Test login endpoint with `curl` - Returns JWT token
  - Test register endpoint with `curl` - Creates user and returns JWT
  - Verify JWT tokens are valid (decode and check payload)
- **Commit**: `backend: Create auth API endpoints with JWT tokens`

#### Step 4: Backend - Add JWT Authentication Decorator

- **Files**: `campaign_ui/app.py`
- **Changes**: 
  - Create `@jwt_required` decorator wrapper
  - Replace `@login_required` with JWT decorator in one test route
- **Verification**:
  - Test protected endpoint without token - Returns 401
  - Test protected endpoint with valid token - Returns 200
  - Test protected endpoint with invalid token - Returns 401
- **Commit**: `backend: Add JWT authentication decorator`

#### Step 5: Backend - Convert Dashboard to API

- **Files**: `campaign_ui/app.py`
- **Changes**: 
  - Convert `GET /dashboard` to `GET /api/dashboard`
  - Return JSON instead of `render_template()`
  - Add JWT authentication
- **Verification**:
  - Test endpoint with `curl` - Returns dashboard stats JSON
  - Verify response structure matches expected format
  - Test without authentication - Returns 401
- **Commit**: `backend: Convert dashboard route to API endpoint`

#### Step 6: Backend - Convert Campaigns List to API

- **Files**: `campaign_ui/app.py`
- **Changes**: 
  - Convert `GET /` (index) to `GET /api/campaigns`
  - Return JSON with campaigns list
- **Verification**:
  - Test endpoint - Returns campaigns JSON array
  - Verify campaign data structure
- **Commit**: `backend: Convert campaigns list to API endpoint`

#### Step 7: Backend - Convert Campaign CRUD to API

- **Files**: `campaign_ui/app.py`
- **Changes**: 
  - Convert campaign routes: GET `/api/campaigns/:id`, POST `/api/campaigns`, PUT `/api/campaigns/:id`, DELETE `/api/campaigns/:id`
  - Convert campaign toggle-active and status endpoints
- **Verification**:
  - Test each CRUD operation with `curl`
  - Verify create/update validation works
  - Verify delete removes campaign
- **Commit**: `backend: Convert campaign CRUD operations to API endpoints`

#### Step 8: Backend - Convert Jobs Routes to API

- **Files**: `campaign_ui/app.py`
- **Changes**: 
  - Convert `GET /jobs`, `GET /jobs/:campaign_id`, `GET /job/:job_id` to API endpoints
  - Convert job status update endpoint
- **Verification**:
  - Test job listing endpoint - Returns jobs JSON
  - Test job details endpoint - Returns job JSON
  - Test status update endpoint - Updates job status
- **Commit**: `backend: Convert job routes to API endpoints`

#### Step 9: Backend - Convert Remaining Routes to API

- **Files**: `campaign_ui/app.py`
- **Changes**: 
  - Convert documents routes
  - Convert account management routes
  - Convert all remaining `render_template()` routes
- **Verification**:
  - Test all endpoints return JSON
  - Verify no `render_template()` calls remain (grep check)
- **Commit**: `backend: Convert all remaining routes to API endpoints`

#### Step 10: Backend - Add React Build Serving Route

- **Files**: `campaign_ui/app.py`
- **Changes**: 
  - Add catch-all route to serve React `index.html` for non-API routes
  - Configure static file serving for React build assets
- **Verification**:
  - Verify API routes still work
  - Verify non-API routes serve React HTML (will work after React build)
- **Commit**: `backend: Add route to serve React SPA`

#### Step 11: Frontend - Initialize React + Vite Project

- **Files**: `campaign_ui/frontend/` (new directory)
- **Changes**: 
  - Run `npm create vite@latest frontend -- --template react`
  - Install dependencies: `react-router-dom`, `@tanstack/react-query`, `axios`
- **Verification**:
  - Run `npm run dev` - Dev server starts
  - Navigate to `http://localhost:5173` - Default React page loads
  - Check browser console - No errors
- **Commit**: `frontend: Initialize React + Vite project with dependencies`

#### Step 12: Frontend - Set Up Project Structure

- **Files**: `campaign_ui/frontend/src/`
- **Changes**: 
  - Create directory structure (components, pages, services, context, utils, assets)
  - Move existing CSS files to `src/assets/css/`
- **Verification**:
  - Verify directory structure exists
  - Verify CSS files copied successfully
- **Commit**: `frontend: Set up project structure and migrate CSS assets`

#### Step 13: Frontend - Create API Client Service

- **Files**: `campaign_ui/frontend/src/services/api.js`
- **Changes**: 
  - Create Axios instance
  - Add request interceptor for JWT token
  - Add response interceptor for 401 handling
  - Export API functions for auth endpoints
- **Verification**:
  - Verify API client can make requests
  - Test interceptor adds token to headers (check Network tab)
  - Test 401 handling redirects to login
- **Commit**: `frontend: Create API client service with JWT token handling`

#### Step 14: Frontend - Create Auth Context

- **Files**: `campaign_ui/frontend/src/context/AuthContext.jsx`
- **Changes**: 
  - Create AuthContext provider
  - Implement login/logout functions
  - Store JWT token in localStorage
  - Provide user state
- **Verification**:
  - Verify AuthContext exports provider and hook
  - Test login function stores token
  - Test logout function clears token
- **Commit**: `frontend: Create AuthContext for user authentication state`

#### Step 15: Frontend - Set Up React Router

- **Files**: `campaign_ui/frontend/src/App.jsx`
- **Changes**: 
  - Configure React Router
  - Add routes: `/login`, `/register`, `/dashboard`, `/campaigns`, etc.
  - Add route guards (require authentication)
  - Add 404 page
- **Verification**:
  - Navigate to each route - Routes work (pages may not exist yet)
  - Test route guards - Unauthenticated users redirected to login
  - Test 404 - Non-existent routes show 404 page
- **Browser Test**: Navigate routes, verify navigation works
- **Commit**: `frontend: Set up React Router with routes and authentication guards`

#### Step 16: Frontend - Create Layout Components

- **Files**: `campaign_ui/frontend/src/components/Layout.jsx`, `campaign_ui/frontend/src/components/Sidebar.jsx`
- **Changes**: 
  - Migrate base layout from `templates/base.html`
  - Migrate sidebar from `templates/components/sidebar.html`
  - Import CSS styles
- **Verification**:
  - Render Layout component - Base structure displays
  - Render Sidebar component - Sidebar displays correctly
  - **Browser Test**: Navigate to page using Layout - Verify layout and sidebar render correctly
- **Commit**: `frontend: Create Layout and Sidebar components`

#### Step 17: Frontend - Create Login Page

- **Files**: `campaign_ui/frontend/src/pages/Login.jsx`
- **Changes**: 
  - Migrate login form from `templates/login.html`
  - Integrate with AuthContext login function
  - Add form validation
  - Handle errors and loading states
- **Verification**:
  - Navigate to `/login` - Login form displays
  - Submit form with valid credentials - Redirects to dashboard, token stored
  - Submit form with invalid credentials - Error message displays
  - **Browser Test**: 
    - Fill login form
    - Submit and verify redirect
    - Check localStorage for token
    - Test error scenarios
- **Commit**: `frontend: Create Login page with authentication`

#### Step 18: Frontend - Create Register Page

- **Files**: `campaign_ui/frontend/src/pages/Register.jsx`
- **Changes**: 
  - Migrate register form from `templates/register.html`
  - Integrate with register API endpoint
  - Add form validation
  - Handle errors and success states
- **Verification**:
  - Navigate to `/register` - Register form displays
  - Submit form - Creates user and redirects to login
  - Test validation - Error messages display for invalid inputs
  - **Browser Test**: Complete registration flow
- **Commit**: `frontend: Create Register page with form validation`

#### Step 19: Frontend - Create Dashboard Page

- **Files**: `campaign_ui/frontend/src/pages/Dashboard.jsx`
- **Changes**: 
  - Migrate dashboard from `templates/dashboard.html`
  - Use React Query to fetch dashboard stats
  - Display stats cards
  - Add loading and error states
- **Verification**:
  - Navigate to `/dashboard` - Dashboard displays (after login)
  - Verify stats fetch correctly from API
  - Verify loading state displays during fetch
  - **Browser Test**: 
    - Login and navigate to dashboard
    - Verify stats cards render correctly
    - Check Network tab - API call succeeds
- **Commit**: `frontend: Create Dashboard page with React Query`

#### Step 20: Frontend - Create Campaigns List Page

- **Files**: `campaign_ui/frontend/src/pages/Campaigns.jsx`
- **Changes**: 
  - Migrate campaigns list from `templates/list_campaigns.html`
  - Fetch campaigns using React Query
  - Display campaigns table/list
  - Add loading and error states
- **Verification**:
  - Navigate to `/campaigns` - Campaigns list displays
  - Verify campaigns fetch from API
  - **Browser Test**: View campaigns list, verify data displays correctly
- **Commit**: `frontend: Create Campaigns list page`

#### Step 21: Frontend - Create Campaign Details Page

- **Files**: `campaign_ui/frontend/src/pages/CampaignDetails.jsx`
- **Changes**: 
  - Migrate campaign details from `templates/view_campaign.html`
  - Fetch campaign data using React Query
  - Display campaign stats and status
  - Implement status polling (React Query refetchInterval)
  - Add DAG trigger functionality
- **Verification**:
  - Navigate to `/campaigns/:id` - Campaign details display
  - Verify status polling works (check Network tab for periodic requests)
  - Test DAG trigger button - Triggers DAG successfully
  - **Browser Test**: 
    - View campaign details
    - Verify status badge updates
    - Test DAG trigger button
    - Verify polling continues
- **Commit**: `frontend: Create Campaign Details page with status polling`

#### Step 22: Frontend - Create Campaign Create/Edit Pages

- **Files**: `campaign_ui/frontend/src/pages/CreateCampaign.jsx`, `campaign_ui/frontend/src/pages/EditCampaign.jsx`
- **Changes**: 
  - Migrate forms from `templates/create_campaign.html` and `templates/edit_campaign.html`
  - Use React Query mutations for create/update
  - Implement form validation
  - Handle ranking weights form section
- **Verification**:
  - Navigate to `/campaigns/create` - Create form displays
  - Submit form - Creates campaign and redirects
  - Navigate to `/campaigns/:id/edit` - Edit form displays with existing data
  - Submit form - Updates campaign
  - **Browser Test**: 
    - Create new campaign
    - Edit existing campaign
    - Verify validation errors display
- **Commit**: `frontend: Create Campaign Create and Edit pages with forms`

#### Step 23: Frontend - Create Jobs List Page

- **Files**: `campaign_ui/frontend/src/pages/Jobs.jsx`
- **Changes**: 
  - Migrate jobs list from `templates/jobs.html`
  - Fetch jobs using React Query
  - Implement filtering and sorting
  - Display jobs table
- **Verification**:
  - Navigate to `/jobs?campaign_id=:id` - Jobs list displays
  - Test filtering - Filters jobs correctly
  - Test sorting - Sorts jobs correctly
  - **Browser Test**: Filter and sort jobs, verify UI updates
- **Commit**: `frontend: Create Jobs list page with filtering and sorting`

#### Step 24: Frontend - Create Job Details Page

- **Files**: `campaign_ui/frontend/src/pages/JobDetails.jsx`
- **Changes**: 
  - Migrate job details from `templates/job_details.html`
  - Fetch job data using React Query
  - Display job information
  - Implement status update
  - Implement notes CRUD
- **Verification**:
  - Navigate to `/jobs/details/:job_id` - Job details display
  - Update job status - Status updates correctly
  - Add/edit/delete notes - Notes CRUD works
  - **Browser Test**: 
    - View job details
    - Update status
    - Add note
    - Edit note
    - Delete note
- **Commit**: `frontend: Create Job Details page with status updates and notes`

#### Step 25: Frontend - Create Documents Page

- **Files**: `campaign_ui/frontend/src/pages/Documents.jsx`
- **Changes**: 
  - Migrate documents page from `templates/documents.html`
  - Implement file upload for resumes and cover letters
  - Display document lists
  - Implement document deletion
- **Verification**:
  - Navigate to `/documents` - Documents page displays
  - Upload resume - File uploads successfully
  - Upload cover letter - File uploads successfully
  - Delete document - Document deleted
  - **Browser Test**: 
    - Upload files
    - Verify files appear in lists
    - Delete files
- **Commit**: `frontend: Create Documents page with file upload`

#### Step 26: Frontend - Create Account Management Page

- **Files**: `campaign_ui/frontend/src/pages/AccountManagement.jsx`
- **Changes**: 
  - Migrate account page from `templates/account_management.html`
  - Display user profile
  - Implement password change form
- **Verification**:
  - Navigate to `/account` - Account page displays
  - Change password - Password updates successfully
  - **Browser Test**: Change password, verify success message
- **Commit**: `frontend: Create Account Management page`

#### Step 27: Frontend - Create Shared Components

- **Files**: `campaign_ui/frontend/src/components/` (various)
- **Changes**: 
  - Create modals (RankingModal, DeleteConfirmModal)
  - Create form components (Input, Select, CheckboxGroup)
  - Create status badges
  - Create loading spinners
  - Create error display components
- **Verification**:
  - Render each component - Components display correctly
  - Test interactive components - Modals open/close, forms submit
  - **Browser Test**: Use components in pages, verify they work
- **Commit**: `frontend: Create shared UI components`

#### Step 28: Frontend - Configure Vite Proxy

- **Files**: `campaign_ui/frontend/vite.config.js`
- **Changes**: 
  - Configure proxy to forward `/api/*` requests to Flask backend
- **Verification**:
  - Start Flask API and React dev server
  - Make API request from React - Request forwarded to Flask
  - Check Network tab - API requests go to correct backend
- **Commit**: `frontend: Configure Vite proxy for API requests`

#### Step 29: Infrastructure - Update Dockerfile for React Build

- **Files**: `campaign_ui/Dockerfile`
- **Changes**: 
  - Multi-stage build: Node.js stage to build React, Python stage for Flask
  - Copy React build output to Flask static directory
- **Verification**:
  - Build Docker image - Build succeeds
  - Run container - Flask serves React build correctly
  - Test in browser - React app loads
- **Commit**: `infra: Update Dockerfile for multi-stage React + Flask build`

#### Step 30: Infrastructure - Update docker-compose.yml

- **Files**: `docker-compose.yml`
- **Changes**: 
  - Update campaign-ui service if needed
  - Ensure environment variables passed correctly
- **Verification**:
  - Run `docker-compose up campaign-ui` - Service starts
  - Navigate to UI - React app loads and works
- **Commit**: `infra: Update docker-compose for React frontend`

#### Step 31: Cleanup - Remove Old Template Files

- **Files**: `campaign_ui/templates/`, `campaign_ui/static/js/`
- **Changes**: 
  - Delete `templates/` directory (React replaces templates)
  - Delete `static/js/` directory (logic migrated to React)
- **Verification**:
  - Verify React app still works without templates
  - Verify no references to deleted files remain
  - **Browser Test**: Test all pages - Everything still works
- **Commit**: `chore: Remove old template and JavaScript files`

#### Step 32: Cleanup - Update Requirements and Documentation

- **Files**: `campaign_ui/requirements.txt`, `README.md`
- **Changes**: 
  - Update requirements.txt (remove flask-login if not needed, ensure JWT/CORS included)
  - Update README with React dev setup instructions
- **Verification**:
  - Verify requirements install correctly
  - Verify README instructions work for new developers
- **Commit**: `docs: Update requirements and README for React migration`

## Considerations

- **Authentication**: JWT tokens stored in httpOnly cookies (more secure) or localStorage
- **Error Handling**: Consistent error responses from API, error boundaries in React
- **Loading States**: Skeleton loaders or spinners during API calls
- **Form Handling**: React Hook Form recommended for complex forms
- **CSS Migration**: Initially import existing CSS files, gradually migrate to CSS modules or styled-components if desired
- **TypeScript**: Consider TypeScript for better type safety (optional, not in scope)
- **Testing**: Add React Testing Library tests (optional, not in scope)

## Verification Summary

Each step must be verified using:

1. **Code Quality**: Linting passes (ruff for Python, ESLint for JS)
2. **Functionality**: Manual testing of the implemented feature
3. **Browser Testing**: Visual verification in browser using browser MCP tools
4. **API Testing**: curl/Postman testing for backend endpoints
5. **Integration**: End-to-end testing of complete flows
6. **CI**: All CI checks pass after push

## Code Review Findings

### High Severity

1. **JWT rate limiting log path can crash**  

The `rate_limit` decorator logs `current_user.user_id` even when JWT auth is used. For JWT-authenticated requests, `current_user` is anonymous, which can raise `AttributeError` and turn a 429 into a 500, effectively disabling rate limiting for JWT flows.

**File**: `campaign_ui/app.py`

**Reference**:

   ```python
   if len(_rate_limit_storage[key]) >= max_calls:
       logger.warning(
           f"Rate limit exceeded for user {current_user.user_id} on {f.__name__}"
       )
       return jsonify(
           {
               "error": f"Rate limit exceeded. Maximum {max_calls} requests per {window_seconds} seconds."
           }
       ), 429
   ```

2. **JWT identity type mismatch in campaign update**  

`get_jwt_identity()` returns a string (token identity is stored as string), but `api_update_campaign` uses it directly for user lookup and permission checks. This can produce false 403s for non-admin users due to string/int mismatch.

**File**: `campaign_ui/app.py`

**Reference**:

   ```python
   user_id = get_jwt_identity()
   user_service = get_user_service()
   user_data = user_service.get_user_by_id(user_id)
   is_admin = user_data.get("role") == "admin" if user_data else False
   ...
   if not is_admin and campaign.get("user_id") != user_id:
       return jsonify({"error": "You do not have permission to update this campaign"}), 403
   ```

### Medium Severity

1. **Legacy template routes remain after React migration**  

The plan marks templates removal as completed, but `render_template` routes are still present. After deleting templates, these routes will error and may conflict with SPA catch‑all routing.

**File**: `campaign_ui/app.py`

**Reference**:

   ```python
   return render_template(
       "dashboard.html",
       active_campaigns_count=active_campaigns_count,
       total_campaigns_count=total_campaigns_count,
       ...
   )
   ...
   @app.route("/")
   @login_required
   def index():
       """List all campaigns (filtered by user, unless admin)."""
   ```

2. **JWT secret key fallback is unsafe for production**  

`JWT_SECRET_KEY` defaults to the Flask `app.secret_key`, which itself defaults to a hardcoded dev string when env vars are missing. This risks insecure JWT signing if deployed without env configuration.

**File**: `campaign_ui/app.py`

**Reference**:

   ```python
   app.secret_key = os.getenv("FLASK_SECRET_KEY") or "dev-secret-key-change-in-production"
   ...
   app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY") or app.secret_key
   ```

### Low Severity

1. **Missing test coverage for new API/auth flows**  

No unit or integration tests were added for JWT auth endpoints and updated API routes. This conflicts with the testing standards in `.cursorrules.mdc` and increases regression risk.