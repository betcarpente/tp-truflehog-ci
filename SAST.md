# TP DevSecOps (Partie 6) : Analyse Statique (SAST) avec Semgrep dans GitHub Actions

## Objectifs pédagogiques

* Comprendre le fonctionnement de l'analyse statique du code source (**SAST**) basée sur les flux (**Source** ➔ **Sanitizer** ➔ **Sink**).
* Déployer un workflow GitHub Actions dédié à Semgrep (`.github/workflows/semgrep.yml`) selon l'architecture **un fichier de workflow par scanner**.
* Configurer des règles Semgrep officielles (`p/default`, `p/owasp-top-ten`) avec une **Quality Gate bloquante** (`--error`).
* Différencier une vraie vulnérabilité (Injection SQL, Command Injection) d'un **faux positif**, et apprendre à le requalifier proprement via commentaire inline (`# nosemgrep`) ou assainissement du flux.
* Exporter les résultats au format standard **SARIF** pour enrichir l'onglet **Security > Code scanning alerts** de GitHub.

---

## Étape 1 : Architecture modulaire des workflows CI/CD

Dans une démarche DevSecOps d'entreprise, on sépare chaque responsabilité d'audit dans un fichier de workflow dédié afin de :
* Isoler les temps d'exécution et les échecs.
* Gérer des droits, des secrets et des déclencheurs spécifiques à chaque outil.
* Maintenir une lisibilité optimale du pipeline.

Arborescence attendue dans votre dépôt :
```text
.github/
└── workflows/
    ├── gitleaks.yml     # Scan de secrets statique (Partie 2)
    ├── trufflehog.yml   # Scan & vérification dynamique de secrets (Partie 4)
    └── semgrep.yml      # Analyse statique SAST du code source (Partie 6)
```

---

## Étape 2 : Créer le workflow dédié `.github/workflows/semgrep.yml`

Créez le fichier de workflow `.github/workflows/semgrep.yml` dans votre dépôt :

```bash
mkdir -p .github/workflows
```

Contenu de `.github/workflows/semgrep.yml` :

```yaml
name: DevSecOps - Semgrep SAST Scan

on:
  push:
    branches: ["main"]
  pull_request:
    branches: ["main"]

permissions:
  contents: read
  security-events: write # Requis pour publier les alertes SARIF dans l'onglet Security de GitHub

jobs:
  semgrep-sast:
    name: Semgrep SAST Quality Gate
    runs-on: ubuntu-latest
    container:
      image: semgrep/semgrep:latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Run Semgrep SAST Analysis
        run: |
          semgrep scan \
            --config "p/default" \
            --config "p/owasp-top-ten" \
            --sarif \
            --output semgrep-results.sarif \
            --error

      - name: Upload SARIF report to GitHub Advanced Security
        uses: github/codeql-action/upload-sarif@v3
        if: always() # Publie le rapport même si Semgrep a trouvé des failles et a échoué
        with:
          sarif_file: semgrep-results.sarif
```

### Points clés de cette configuration :
* **Un workflow dédié** : Ce job ne dépend ni de GitLeaks ni de TruffleHog ; il s'exécute en parallèle dans la CI.
* `container: image: semgrep/semgrep:latest` : Exécution sous conteneur officiel pour garantir la reproductibilité et la rapidité du scan sans installation de dépendances locales.
* `--config "p/default" --config "p/owasp-top-ten"` : Règles communautaires et industrielles couvrant les failles de sécurité majeures (injections, cryptographie faible, mauvaise gestion de sessions).
* `--error` : Définit la **Quality Gate**. Semgrep renvoie un code de sortie non-nul (code `1`) si des vulnérabilités de sévérité bloquante sont détectées, ce qui fait échouer le build sur la PR.
* `--sarif & upload-sarif` : Standardise la remontée des failles directement dans l'interface de GitHub (**Security** > **Code scanning**).

Commitez et poussez ce workflow :

```bash
git add .github/workflows/semgrep.yml
git commit -m "ci: add dedicated semgrep sast workflow"
git push origin main
```

---

## Étape 3 : Simuler des vulnérabilités applicatives (SQL Injection & Command Injection)

1. Créez une nouvelle branche pour tester le scanner :
```bash
git checkout -b feature/user-api
```

2. Créez un fichier applicatif `server.py` contenant des failles intentionnelles caractérisées par une absence de sanitization entre l'entrée utilisateur (**Source**) et l'exécution (**Sink**) :

```python
# server.py
import sqlite3
import os
from flask import Flask, request

app = Flask(__name__)

@app.route("/user")
def get_user():
    user_id = request.args.get("id")
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # FAILLE 1 (SQL Injection) : Concaténation directe d'une variable non assainie dans une requête SQL
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
    return cursor.fetchall()

@app.route("/ping")
def ping_host():
    target = request.args.get("ip")
    # FAILLE 2 (Command Injection) : Passage direct de l'input utilisateur au shell système
    os.system("ping -c 1 " + target)
    return "Ping triggered"

if __name__ == "__main__":
    app.run(port=5000)
```

3. Commitez et poussez cette branche :
```bash
git add server.py
git commit -m "feat: add user query and diagnostic endpoints"
git push origin feature/user-api
```

4. Ouvrez une **Pull Request** vers `main`.
5. Observez l'encart des checks GitHub Actions :
* Le job **Semgrep SAST Quality Gate** passe au **rouge** (❌).
* Cliquez sur **Details** ou sur l'onglet **Security > Code scanning** : Semgrep liste les règles déclenchées (ex: `python.lang.security.injection.tainted-sql-string`, `python.lang.security.injection.os-system`).

---

## Étape 4 : Requalification et Remédiation (Vrai Positif vs Faux Positif)

En entreprise, un Security Champion ou Ingénieur AppSec doit adopter une démarche méthodique :
1. **Corriger les vrais positifs** en utilisant les bonnes pratiques de programmation sécurisée.
2. **Requalifier les faux positifs / exceptions** de façon argumentée et traçable.

### 1. Correction du vrai positif (SQL Injection)
Pour éliminer l'injection SQL, on utilise une requête préparée avec des paramètres liés (*Parameterized Query*) qui neutralise toute tentative d'injection :

```python
# Remplacement sécurisé dans server.py :
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

### 2. Gestion et documentation d'un faux positif / exception avec `# nosemgrep`
Supposons que pour le diagnostic réseau interne, la fonction de ping soit réservée aux administrateurs avec un input préalablement validé par une regex stricte d'adresse IPv4, et que l'équipe AppSec autorise l'exception.

On documente l'exception directement sur la ligne ciblée en précisant la règle ignorée et la justification :

```python
# nosemgrep: python.lang.security.injection.os-system -- Justification AppSec : Input validé en amont via regex IPv4 stricte
os.system("ping -c 1 " + target)
```

Mettez à jour `server.py` :

```python
# server.py (Version corrigée et requalifiée)
import sqlite3
import os
import re
from flask import Flask, request, abort

app = Flask(__name__)

@app.route("/user")
def get_user():
    user_id = request.args.get("id")
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # CORRECTION : Requête paramétrée (Sanitizer intégré)
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cursor.fetchall()

@app.route("/ping")
def ping_host():
    target = request.args.get("ip")
    # Validation stricte par Regex (Whitelist)
    if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", target or ""):
        abort(400, "Invalid IP address")
    
    # nosemgrep: python.lang.security.injection.os-system
    os.system("ping -c 1 " + target)
    return "Ping triggered"

if __name__ == "__main__":
    app.run(port=5000)
```

3. Commitez et poussez le correctif :
```bash
git add server.py
git commit -m "fix: sanitize sql query and document validated os.system rule"
git push origin feature/user-api
```

4. Retournez sur la Pull Request : le workflow **Semgrep SAST Scan** se réexécute et passe au **vert** (✅).

---

### Questions d'analyse :

1. **Théorie des flux :** Dans l'exemple initial de la route `/user`, identifiez précisément quelle variable constitue la **Source**, quel appel représente le **Sink**, et pourquoi l'absence de **Sanitizer** rend l'application vulnérable.
2. **Architecture CI/CD :** Pourquoi est-il préférable d'avoir un fichier `.github/workflows/semgrep.yml` séparé de `.github/workflows/gitleaks.yml` plutôt qu'un seul gigantesque fichier `security.yml` qui exécuterait tous les scanners séquentiellement ?
3. **Gouvernance AppSec :** Pourquoi l'usage de la directive `nosemgrep` doit-il être impérativement associé à un audit régulier (ex: `semgrep --show-suppressed`) et soumis à validation par un Security Champion ?

---

### Livrable attendu

* Une capture d'écran de l'arborescence `.github/workflows/` montrant vos fichiers de scanners distincts (`gitleaks.yml`, `trufflehog.yml`, `semgrep.yml`).
* Une capture d'écran du workflow Semgrep en **échec** (❌) sur la Pull Request avec le détail des alertes détectées.
* Une capture d'écran du workflow repassé au **vert** (✅) après correction de l'injection SQL et documentation de l'exception `nosemgrep`.
* Les réponses rédigées aux 3 questions d'analyse.
 