# Guide complet `.waypoints` pour missions MAVLink

## Référence de position (`frame`)

Le champ `frame` détermine **comment interpréter la position (surtout l'altitude)** du waypoint.
Il est essentiel pour que le drone vole correctement et en sécurité.

| Valeur | Nom MAVLink                     | Signification                                                            |
| ------ | ------------------------------- | ------------------------------------------------------------------------ |
| `0`    | `MAV_FRAME_GLOBAL`              | Coordonnées absolues, **altitude par rapport au niveau de la mer** (MSL) |
| `3`    | `MAV_FRAME_GLOBAL_RELATIVE_ALT` | Coordonnées absolues, **altitude relative au point de décollage** (AGL)  |
| `10`   | `MAV_FRAME_LOCAL_NED`           | Coordonnées locales (rarement utilisées en mission `.waypoints`)         |

---

### Différences entre `frame = 0` (absolue) et `frame = 3` (relative)

| Attribut             | `frame = 0` – Absolue (MSL)                              | `frame = 3` – Relative (AGL)                                    |
| -------------------- | -------------------------------------------------------- | --------------------------------------------------------------- |
| Latitude / Longitude | Absolues (WGS84)                                         | Absolues (pareil)                                               |
| Altitude             | Par rapport au **niveau de la mer (MSL)**                | Par rapport au **sol du point de décollage (AGL)**              |
| Usage                | Missions précises, avions habités, vols à haute altitude | 🟢 **Recommandé** pour les drones classiques, tests, inspection |
| Risque               | Peut voler trop bas ou haut si terrain inconnu           | Moins risqué, altitude relative plus intuitive                  |

---

## Structure d’un fichier `.waypoints` (format QGC WPL 110)

Ce fichier est lu par Mission Planner, QGroundControl, etc.

### Exemple de fichier `.waypoints`

```
QGC WPL 110
0	1	0	16	0	0	0	0	-35.3632621	149.1652374	584.09	1
1	0	3	22	0	0	0	0	-35.3630000	149.1650000	50.00	1
2	0	3	16	0	0	0	0	-35.3620000	149.1660000	50.00	1
3	0	3	21	0	0	0	0	-35.3610000	149.1670000	0.00	1
```

---

### Détail des champs (colonnes)

| Champ          | Exemple          | Signification                                                 |
| -------------- | ---------------- | ------------------------------------------------------------- |
| `seq`          | `0`, `1`, `2`    | Numéro du waypoint                                            |
| `current`      | `1` ou `0`       | `1` = point de départ (uniquement pour le 1er), `0` sinon     |
| `frame`        | `0` ou `3`       | Référence de position (voir tableau `frame` ci-dessus)        |
| `command`      | `16`, `22`, `21` | Code MAVLink : `16` = WAYPOINT, `22` = TAKEOFF, `21` = LAND   |
| `param1-4`     | `0.0`            | Paramètres spécifiques à la commande (angle, délai, etc.)     |
| `lat`          | `-35.3632621`    | Latitude en degrés décimaux (WGS84)                           |
| `lon`          | `149.1652374`    | Longitude en degrés décimaux (WGS84)                          |
| `alt`          | `50.0`           | Altitude, interprétée selon `frame`                           |
| `autocontinue` | `1` ou `0`       | `1` = le drone passe au WP suivant automatiquement, `0` sinon |

---

### Erreurs fréquentes

* La **première ligne** doit toujours être exactement : `QGC WPL 110`
* Les colonnes sont **séparées par tabulation (`\t`)**, pas des espaces !
* N’utilise pas de caractères spéciaux ou de séparateurs ambigus.
* Pour un vol simple, préfère `frame = 3` et `command = 16`, `22`, `21`