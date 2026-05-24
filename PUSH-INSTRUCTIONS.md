# Push to GitHub — instructions Tom

> Ces 2 demos sont prêtes à être publiées sur ton compte GitHub `Lupin133`. L'orchestrateur Kairos ne pousse pas tout seul (action engageante sur ton compte perso = HITL).

## 1. Créer le repo public

Sur https://github.com/new :
- Owner : `Lupin133`
- Repository name : `limier-demos`
- Description : `Limier — Python B2B data extraction demos (Scrapling, French gov APIs)`
- Visibility : **Public**
- **DO NOT** initialize with README / LICENSE / .gitignore (on a déjà tout)

Tu peux le faire via `gh` CLI si installé :

```bash
gh repo create Lupin133/limier-demos --public --description "Limier — Python B2B data extraction demos (Scrapling, French gov APIs)"
```

## 2. Push depuis le workspace local

```powershell
cd "C:\Users\cauba\Documents\Projets Dev\Claude travail\kairos\release-limier"

git init -b main
git add .
git commit -m "feat: Limier portfolio v1.0 — demo1 Sirene enrichment + demo2 CNB avocats"

git remote add origin https://github.com/Lupin133/limier-demos.git
git push -u origin main
```

## 3. Vérifier

Ouvre https://github.com/Lupin133/limier-demos — le README doit s'afficher.

## 4. Mettre à jour le profil Upwork

Une fois le repo public, ajoute le lien dans la bio Upwork (section "Portfolio") :
- URL : `https://github.com/Lupin133/limier-demos`
- Label : `Portfolio: Python scraping & B2B data extraction demos`

C'est le seul changement à faire sur Upwork pour Phase 2. Les autres changements profil (title/bio/skills/tarif/catégorie) sont dans `stories/Limier/SetupProfil-v0.1.md` section 3.

## Coût

- Création repo : 0€
- Push : 0€
- Hébergement GitHub public : gratuit

## Durée

5-10 minutes max.
