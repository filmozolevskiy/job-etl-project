# Frontend - React SPA

This is the React Single Page Application (SPA) frontend for the Job Search Manager.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Start development server:
```bash
npm run dev
```

The development server will run on `http://localhost:5173` with a proxy to the Flask backend at `http://localhost:5000`.

## Build

Build the production bundle:
```bash
npm run build
```

The built files will be in the `dist/` directory and will be served by the Flask backend.

## Tech Stack

- **React 19** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **React Router** - Client-side routing
- **TanStack Query** - Server state management
- **Axios** - HTTP client
- **JWT** - Authentication tokens

## Project Structure

```
frontend/
├── src/
│   ├── components/     # Reusable UI components
│   ├── pages/          # Page components
│   ├── services/       # API client and services
│   ├── contexts/       # React contexts (Auth, etc.)
│   ├── types/          # TypeScript type definitions
│   └── assets/         # Static assets (CSS, images)
├── dist/               # Production build output
└── package.json
```

## Environment Variables

Create a `.env` file in the frontend directory (optional, defaults work for local dev):

```
VITE_API_URL=http://localhost:5000
```
