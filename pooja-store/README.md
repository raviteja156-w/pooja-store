# PrepMate AI - Interview Prep Coach (Groq + Flask)
Mobile-first AI coach: 30-min revision, 15-min test (quiz + voice definitions + grammar fix), 5 daily coding problems, adaptive tasks/resources, resume analysis.

## Run locally
    pip install -r requirements.txt
    cp .env.example .env   # add GROQ_API_KEY, then: export $(cat .env | xargs)
    python app.py          # http://localhost:5000

## Deploy on Render
1. Push this folder to GitHub.
2. Render > New > Blueprint (uses render.yaml) or Web Service.
3. Add env var GROQ_API_KEY. Deploy.
Note: free Render disk is ephemeral, so progress (SQLite) resets on redeploy. Set DB_PATH to a persistent disk path or use Render Postgres for permanence.
Voice input needs Chrome/Edge/Android Chrome (Web Speech API) and HTTPS (Render provides it).
