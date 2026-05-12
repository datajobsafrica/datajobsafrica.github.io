import json
from datetime import date

JSON_FILE = r"C:\Users\fokam\OneDrive\Bureau\DataJobsAfrica\datajobsafrica.github.io\offres.json"

with open(JSON_FILE, "r", encoding="utf-8") as f:
    jobs = json.load(f)

today = date.today()
modifications = 0

for job in jobs:
    if job.get("isNew") and job.get("date"):
        try:
            p = job["date"].split("/")
            date_job = date(int(p[2]), int(p[1]), int(p[0]))
            age = (today - date_job).days
            if age >= 1:
                job["isNew"] = False
                modifications += 1
                print(f"isNew = False pour : {job['title']} (âge {age} jour(s))")
        except Exception as e:
            print(f"Erreur pour {job.get('title')}: {e}")

if modifications > 0:
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    print(f"\n✅ {modifications} offre(s) mise(s) à jour (isNew = False)")
else:
    print("✅ Aucune modification nécessaire")