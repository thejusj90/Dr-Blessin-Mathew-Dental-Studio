# Dr. Blessin's Dental Studio — Patient Records

## Deploy to Vercel (5 minutes)

### Step 1 — Push to GitHub
1. Go to github.com → New repository → Name: `drblessins-records` → Private → Create
2. On your computer, open Terminal and run:
```
git init
git add .
git commit -m "Initial deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/drblessins-records.git
git push -u origin main
```

### Step 2 — Deploy on Vercel
1. Go to vercel.com → Sign in with GitHub
2. Click "Add New Project"
3. Import `drblessins-records` from GitHub
4. Under "Root Directory" set to: `public`
5. Click Deploy

### Step 3 — Done
Your app will be live at: `https://drblessins-records.vercel.app`

## Install on iPad as App
1. Open the URL in Safari
2. Tap the Share button (box with arrow)
3. Tap "Add to Home Screen"
4. Tap Add — it now works like a native app

## Features
- Search patients by name, phone, or Patient ID
- Log new visits with full details
- Editable patient directory
- All records with filters
- Overview charts by year
- Merge duplicate patients
- Works offline — syncs when internet returns

## Data
- Database: Supabase (Mumbai region)
- 847 patients, 1,661 visits loaded
- All new data saves directly to Supabase
