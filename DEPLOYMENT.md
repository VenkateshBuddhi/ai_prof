# Vercel Deployment Guide for AI.Prof Frontend

This project contains a Next.js 16 App Router frontend located in the [`frontend/`](./frontend) directory.

---

## 🚀 Option 1: Deploy via Vercel Web Dashboard (Recommended)

### Step 1: Push the Repository to GitHub
Make sure your latest code is pushed to your GitHub repository:
```bash
git add .
git commit -m "feat: complete multi-tenant healthcare frontend"
git push origin main
```

### Step 2: Import into Vercel
1. Log in to [vercel.com](https://vercel.com) and click **"Add New..." -> "Project"**.
2. Select your GitHub repository (`ai_prof` / `VenkateshBuddhi/ai_prof`).

### Step 3: Configure Project Settings
In the Vercel project configuration screen:
- **Project Name**: `ai-prof-frontend` (or your preferred name)
- **Framework Preset**: `Next.js`
- **Root Directory**: Click **Edit** and select **`frontend`** 👈 *(Crucial step)*

### Step 4: Add Environment Variables (Optional for full backend integration)
Under the **Environment Variables** section, you can optionally configure:
- `NEXT_PUBLIC_SUPABASE_URL` = `https://your-supabase-project.supabase.co`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` = `your-supabase-anon-key`
- `NEXT_PUBLIC_API_URL` = `https://your-backend-api.com`

*(Note: If environment variables are omitted initially, the frontend will automatically use fallback mock data and client safeguards so the build and UI preview will succeed cleanly).*

### Step 5: Click "Deploy"
Vercel will install dependencies, build the Next.js production bundle, and provide you with a live `.vercel.app` production URL!

---

## ⚡ Option 2: Deploy via Vercel CLI

If you have the Vercel CLI installed:
```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Login to Vercel (if not already logged in)
npx vercel login

# 3. Deploy Preview
npx vercel

# 4. Deploy Production
npx vercel --prod
```
