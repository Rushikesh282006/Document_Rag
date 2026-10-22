# Groundwork Frontend (Web Client)

The modern, responsive web application for the **Multi-Tenant Document RAG Platform**. Built with **React 19**, **TypeScript**, **Vite**, **TanStack Router**, and **Tailwind CSS v4**.

---

## Features

- **Multi-Tenant Workspace**: Secure user registration and login with JWT session management stored in `localStorage`.
- **Document Management**:
  - Upload PDF files with file size checking (up to 50MB).
  - Track background processing status with interactive status badges (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`).
  - Scoped document selection (select specific PDFs to constrain RAG query context).
  - Document deletion with cascading chunk removal.
- **Real-Time Streaming Chat**:
  - Live token streaming via Server-Sent Events (SSE).
  - Structured sources and citations emitted upfront before token generation starts.
  - Markdown message rendering with GitHub Flavored Markdown (GFM) and syntax highlighting via `rehype-highlight`.
- **Interactive Citation Inspector**:
  - Click any citation reference (`[1]`, `[2]`) in the chat to open a detailed sidebar or mobile sheet.
  - Shows source document name, exact page number, RRF relevance score meter, and the cited text snippet.
- **Dual Live & Mock Mode**:
  - **Live Mode**: Communicates with the FastAPI backend via REST and SSE.
  - **Mock Mode**: Fully client-side mock simulation allowing demo and offline evaluation.
- **Responsive Layout**: Collapsible sidebar on desktop and sliding drawer sheets on mobile devices.

---

## Tech Stack

| Technology | Purpose |
| :--- | :--- |
| **React 19** | Core UI library |
| **TypeScript 5.8** | Static type checking and safety |
| **Vite 8** | Dev server and production build pipeline |
| **TanStack Router / Start** | Type-safe client routing and layout management |
| **Tailwind CSS v4** | Utility-first responsive design tokens |
| **Radix UI** | Accessible, unstyled primitives (Dialogs, Sheets, Popovers, Accordions) |
| **Lucide React** | Icons |
| **Vitest & React Testing Library** | Unit and integration testing |

---

## Project Structure

```text
frontend/
├── public/                    # Static public assets
├── src/
│   ├── components/            # UI components
│   │   ├── ui/                # Reusable Radix UI & styled primitives (button, sheet, etc.)
│   │   ├── workspace/         # Main workspace modules
│   │   │   ├── Chat.tsx       # Chat stream interface, citation pills, message list
│   │   │   └── DocumentSidebar.tsx # PDF upload, document list, selection filters
│   │   ├── AuthForm.tsx       # User login & registration forms
│   │   └── ModeSwitch.tsx     # Toggle between Live API and Mock simulation
│   ├── hooks/                 # Custom React hooks (use-mobile, etc.)
│   ├── lib/                   # Core application utilities
│   │   ├── api.ts             # API client, Mock engine, and SSE parser
│   │   ├── auth.tsx           # Authentication Context & user state
│   │   └── utils.ts           # Class merge and format helpers
│   ├── routes/                # File-based routes
│   │   ├── __root.tsx         # Root layout shell and meta tags
│   │   ├── index.tsx          # Main workspace & citation inspector route
│   │   ├── login.tsx          # Authentication login route
│   │   └── register.tsx       # New user sign-up route
│   ├── styles.css             # Tailwind CSS tokens & color variables
│   └── test/                  # Test suites (SSE handling, routing)
├── .env.example               # Environment variables template
├── package.json               # NPM packages and build scripts
└── vite.config.ts             # Vite configuration
```

---

## Getting Started

### 1. Install Dependencies
```bash
npm install
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Set the backend API URL:
```env
VITE_API_BASE_URL="http://localhost:8000/api/v1"
```

### 3. Start Development Server
```bash
npm run dev
```
Open your browser at [http://localhost:5173](http://localhost:5173).

---

## Available Scripts

| Command | Action |
| :--- | :--- |
| `npm run dev` | Starts the Vite development server with Hot Module Replacement (HMR) |
| `npm run build` | Compiles TypeScript and creates an optimized production build in `dist/` |
| `npm run preview` | Locally preview the production build |
| `npm run test` | Runs the test suite with Vitest |
| `npm run test:watch` | Runs tests in watch mode |
| `npm run lint` | Runs ESLint across the codebase |
| `npm run format` | Formats code with Prettier |

---

## Server-Sent Events (SSE) Protocol

When querying the RAG endpoint, the frontend consumes an SSE stream:

1. **`event: sources`**: Contains an array of citations retrieved via Reciprocal Rank Fusion.
   ```json
   {
     "citations": [
       {
         "document_id": "...",
         "document_name": "example.pdf",
         "page": 2,
         "score": 0.032,
         "snippet": "..."
       }
     ]
   }
   ```
2. **`event: token`**: Emits real-time tokens from the LLM.
   ```json
   { "token": "word" }
   ```
3. **`event: end`**: Signals completion of generation.
   ```json
   { "status": "completed" }
   ```
