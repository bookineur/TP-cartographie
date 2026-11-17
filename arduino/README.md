# Programmes de l'ESP32 et du lidar LD06

## Version de référence : `ESP32_robot_wifi_v5`

C'est la version retenue pour le robot : la plus fiable pendant les essais, notamment avec le partage de
connexion du téléphone.

- **Réseau** : rejoint le Wi-Fi défini dans `wifi_secrets.h` (box ou partage de connexion, 2,4 GHz) ;
  sans réponse en 15 s, crée son réseau de secours (192.168.4.1). Répond aussi à `http://robot-lidar.local`.
- **Lidar** : LD06 sur GPIO33 (PWM sur GPIO32) ; `GET /scan` renvoie le dernier tour complet en CSV
  (`angle_deg,distance_mm,intensity`), avec l'indicateur `moving=0/1`.
- **Moteurs** : `/drive?l=..&r=..` (rampe de démarrage), `/turn?deg=..` (renvoie la durée en ms), `/stop`.
- **Sécurité** : sans ordre depuis 0,5 s, le robot ralentit et s'arrête.
- **Lidar Lab** : le serveur du PC (`node serveur_robot/serveur.js`) trouve le robot tout seul.

Installation : copier `ESP32_robot_wifi_v5/wifi_secrets_exemple.h` en `wifi_secrets.h` dans le même
dossier, y mettre le nom et le mot de passe du réseau, puis téléverser avec le noyau ESP32 3.x.
`wifi_secrets.h` est ignoré par Git : le mot de passe n'est jamais versionné.

## Autres versions (conservées pour l'historique)

| Dossier | Contenu |
|---|---|
| `LD06_capture`, `ESP32_LD06_CSV_v2`, `ESP32_LD06_CSV_intensite` | Lecture du LD06 et envoi des tours en CSV sur le port série (Jour 1) |
| `ESP32_robot_wifi_v1` à `v4` | Étapes successives : réseau du robot et pilotage depuis le téléphone (v1, v2), grid map sur le téléphone (v3), liaison avec Lidar Lab sur le PC (v4) |
| `ESP32_robot_wifi_v6` | Reconnexion automatique au Wi-Fi si la connexion tombe |
| `ESP32_robot_wifi_v7` | Le robot crée directement son propre réseau, sans chercher d'autre Wi-Fi |
