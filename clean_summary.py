import json

with open('offres.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f)

for job in jobs:
    if 'summary' in job:
        # Supprime " Full posting: ..."
        if 'Full posting:' in job['summary']:
            job['summary'] = job['summary'].split(' Full posting:')[0]
        
        # Supprime " Apply on the company's official website."
        if ' Apply on the company\'s official website.' in job['summary']:
            job['summary'] = job['summary'].replace(' Apply on the company\'s official website.', '')
        
        # Supprime aussi la version sans apostrophe (au cas où)
        if ' Apply on the companys official website.' in job['summary']:
            job['summary'] = job['summary'].replace(' Apply on the companys official website.', '')

with open('offres.json', 'w', encoding='utf-8') as f:
    json.dump(jobs, f, ensure_ascii=False, indent=2)

print("✅ Nettoyé !")