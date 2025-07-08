
.

## 🛠️ Documentation – `create` dans `mission_tool.py`

### Objectif

La commande `create` permet de générer un fichier de mission (`.waypoints`) au format compatible avec **QGroundControl (QGC)**. Ce fichier peut ensuite être utilisé pour envoyer une mission à un drone via MAVLink.

----------

### Format de fichier généré

Le fichier généré suit le format QGC WPL 110 :

`QGC WPL 110
0    1    0    16    0.00000000    0.00000000    0.00000000    0.00000000    -35.36326210    149.16523740    584.090000    1
1    0    3    22    0.00000000    0.00000000    0.00000000    0.00000000    0.00000000    0.00000000    100.000000    1 ...` 

Chaque ligne représente un **waypoint** contenant :

-   `seq` : Numéro de séquence
    
-   `current` : Indique si c’est le WP actif
    
-   `frame` : Référence du repère (0 = global, 3 = global relative alt)
    
-   `command` : Type d’action (16 = NAV_WAYPOINT, 22 = TAKEOFF, 21 = LAND, etc.)
    
-   `param1` à `param4` : Paramètres spécifiques à la commande
    
-   `lat`, `lon`, `alt` : Latitude, longitude, altitude
    
-   `autoContinue` : Si le drone continue automatiquement au WP suivant
    

----------

### Waypoints par défaut

Si vous ne fournissez pas de liste personnalisée, le script utilise 4 waypoints de base :

1.  **Home** : Position de départ
    
2.  **Décollage** : Altitude 100m
    
3.  **Waypoint** : Vers une position cible
    
4.  **Atterrissage** : Altitude 0m
    

----------

### Utilisation

`python mission_tool.py create mission1.waypoints` 

Cela va :

-   Générer le fichier `mission1.waypoints` dans le répertoire courant.
    
-   Écrire les 4 waypoints par défaut dedans.
    
-   Afficher un message de confirmation.
    

----------

### Personnalisation

Vous pouvez adapter la fonction `create_mission(filename, waypoints)` pour passer une liste personnalisée de waypoints depuis un autre script Python.

Exemple :
`custom_wp = [
    { "seq": 0, "current": 1, "frame": 3, "command": 22, "param1": 15, "param2": 0, "param3": 0, "param4": 0, "lat": 48.8566, "lon": 2.3522, "alt": 100.0, "autoContinue": 1 },
    ...
]
create_mission("custom.waypoints", custom_wp)` 