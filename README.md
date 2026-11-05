# data-lille.fr Linktree

Inspired from https://github.com/lironmiz/Link-Tree 

data-lille.fr link tree website page built by html and css only to group all our profiles on social networks in one web page.

Hosted on netlify.


## Mise à jour des meetups

Les meetups (prochain meetup, tableau, chiffres clés) sont générés dans `index.html` par
`scripts/maj_meetups.py` à partir de `meetups.json` et de meetup.com/data-lille.

- Automatique : la GitHub Action `.github/workflows/maj-meetups.yml` tourne chaque vendredi et ouvre
  (ou met à jour) une PR unique sur la branche `auto/meetups`, seulement s'il y a un changement.
- À la main : `python3 scripts/maj_meetups.py`, ou bouton « Run workflow » dans l'onglet Actions.
- Pour corriger un lieu (ex. adresse → nom de l'entreprise), modifier `venue` dans `meetups.json` :
  le script ne réécrit jamais le lieu d'un meetup déjà connu.
- Ne pas modifier à la main le HTML entre les repères `<!-- auto:... -->`, il est régénéré.
