# Frontend Hosting & Deployment Specification

## 1. Evaluation of Vercel Free (Hobby) Plan

### 1.1 Commercial vs. Non-Commercial Policy
- Vercel's Hobby plan explicitly permits **personal, non-commercial use**.
- A private trading dashboard operated solely by an individual trader to monitor personal paper and live trading—with zero subscription fees, zero advertising, zero client billing, and no monetization—**fully complies with the Vercel Hobby terms of service**.

### 1.2 Architectural Decoupling: Why Vercel is Safe for the UI
- **Critical Design Choice:** Vercel is used **exclusively to host the static React/TypeScript Single Page Application (SPA)** assets (HTML, CSS, JS bundles).
- **No Long-Running Serverless Functions on Vercel:** We **never** run trading algorithms, WebSocket listeners, or stateful order loops on Vercel serverless functions.
- All persistent trading logic, scheduling, broker connections, and WebSockets reside on the **Oracle Always Free VM**.
- This architectural decoupling guarantees that the frontend is 100% serverless-rate-limit free and costs ₹0.

---

## 2. Zero-Cost Free Alternatives to Vercel

If the user prefers alternative hosting or if regional DNS latency is a factor:
1. **Cloudflare Pages:**
   - 100% Free for personal and commercial static sites.
   - Unlimited bandwidth and requests.
   - Built-in global CDN with sub-10ms edge caching across India (Mumbai, Delhi, Chennai, Bangalore, Kolkata edge nodes).
2. **GitHub Pages:**
   - Completely free static hosting directly from the GitHub repository (`gh-pages` branch).
   - Automated deployment via GitHub Actions.

Both options support client-side routing for React Router (`/* -> /index.html`).

---

## 3. Security Boundary: Zero Client-Side Secrets

The frontend codebase and environment variables (`.env.production`) contain **ZERO broker secrets**:
- `VITE_SUPABASE_URL`: Public Supabase Project URL.
- `VITE_SUPABASE_ANON_KEY`: Public anonymous API key (secured via Database Row Level Security).
- `VITE_API_BASE_URL`: HTTPS URL of the FastAPI backend running on Oracle Cloud.

Angel One API Keys, Client Secrets, MPINs, TOTP Secrets, and Supabase Service Role keys **never touch the browser**.
