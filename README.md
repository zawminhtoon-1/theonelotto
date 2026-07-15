# TheOneLotto

Japan Loto 6 draw results website — Next.js frontend backed by Neon DB (PostgreSQL).

## Pages

| Route | Description |
|---|---|
| `/` | Latest draw result + last 20 draws |
| `/predictions` | 5 formula-based picks for the next draw, verified against full history |
| `/history` | All 2,119+ historical draws |

## Stack

- **Frontend:** Next.js 15, TypeScript, Tailwind CSS v4
- **Database:** Neon (PostgreSQL 17) via `@neondatabase/serverless`
- **Data source:** Mizuho Bank CSV files (scraped by Temporal.io workflow)
- **Deploy:** Vercel

## Local development

```bash
cp .env.local.example .env.local
# Fill in DATABASE_URL in .env.local

npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Vercel deployment

1. Push this repo to GitHub
2. Import in Vercel
3. Add `DATABASE_URL` as an Environment Variable in Vercel project settings
4. Deploy

## Scraper

Draw results are fetched automatically by a Temporal.io workflow (`loto6_scraper_workflow.py`) running on a home server. The workflow fires every Monday and Thursday at 23:00 JST and updates the Neon DB.
