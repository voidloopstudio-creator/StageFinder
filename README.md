# StageFinder Ads

Générateur de pubs vidéo quotidiennes (30 s, 1080×1920, style motion design) pour Stage Finder.

- `engine/ad.html` : animation (HTML/CSS/JS déterministe, `render(t)`), pilotée par `engine/cfg.js` (généré).
- `engine/variants.json` : banque d'accroches, secteurs, élèves, titres, mots, slogans, légendes, hashtags.
- `engine/music.py` : instrumentale originale 142 BPM générée par code (aucun droit d'auteur tiers).
- `engine/generate.py` : choisit les variantes (rotation « le moins récemment utilisé »), génère musique, rendu, MP4, légende.
- `data/history.json` : historique des combinaisons déjà utilisées (évite les répétitions).

Lancer : `python3 -I engine/generate.py` (≈ 1 min 30). Sortie dans `out/` (ignoré par git).
Prérequis : Python 3 + numpy + playwright (Chromium), ffmpeg.
Le slogan et la mention « Disponible le 1er novembre » s'adaptent à la date (compte à rebours, puis « Disponible maintenant »).
