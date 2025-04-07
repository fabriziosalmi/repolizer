# Parametri di Valutazione di Repolizer

Questo documento descrive in dettaglio i parametri utilizzati da Repolizer per valutare i repository GitHub. Ogni parametro ha un peso configurabile che può essere adattato alle specifiche esigenze del progetto.

## Scala dei Pesi

I pesi sono configurati su una scala da 1 a 5:

- **1**: Importanza Bassa
- **2**: Importanza Media-Bassa
- **3**: Importanza Media
- **4**: Importanza Alta
- **5**: Importanza Altissima

## Categorie e Parametri

### Popolarità & Impatto

| Parametro | Descrizione | Metodo di Misurazione | Peso (Esempio) |
|-----------|-------------|------------------------|----------------|
| Stelle (Stars) | Indicatore diretto di apprezzamento e visibilità | API GitHub (Conteggio) | 4 |
| Forks | Interesse nel modificare/usare il codice come base | API GitHub (Conteggio) | 4 |
| Watchers | Interesse nel seguire attivamente gli aggiornamenti | API GitHub (Conteggio) | 2 |
| Contributori (Numero) | Ampiezza della base di sviluppo (può indicare complessità o community) | API GitHub (Conteggio lista contributori) | 2 |
| Dipendenti (Dependents) | Impatto reale: quanti altri progetti si basano su questo | API GitHub ("Used by"), API Package Manager (npm, PyPI, etc.) | 5 |

### Attività & Manutenzione

| Parametro | Descrizione | Metodo di Misurazione | Peso (Esempio) |
|-----------|-------------|------------------------|----------------|
| Data Ultimo Commit | Recency dello sviluppo; indica se il progetto è ancora vivo | API GitHub | 5 |
| Frequenza Commit | Regolarità e intensità dello sviluppo nel tempo | API GitHub (analisi storico commit con script Python) | 4 |
| Release/Tag Frequenza | Regolarità nel fornire versioni stabili e ben definite | API GitHub (analisi date tag/release) | 4 |
| Attività Issues (Ratio Open/Closed) | Capacità di gestire e risolvere i problemi segnalati | API GitHub (conteggio e analisi stato issues) | 4 |
| Attività Issues (Tempo Chiusura) | Reattività del team di manutenzione ai problemi | API GitHub (analisi timestamp issue con script Python) | 4 |
| Attività PR (Ratio Open/Merged) | Capacità di integrare contributi esterni | API GitHub (conteggio e analisi stato PR) | 4 |
| Attività PR (Tempo Chiusura/Merge) | Velocità nell'integrare o dare feedback sulle proposte di modifica | API GitHub (analisi timestamp PR con script Python) | 4 |
| Distribuzione Contributi | Indica se il progetto dipende da pochi "key contributors" (Bus Factor) | API GitHub (analisi numero commit/linee per contributore con script Python) | 3 |
| Stato Archivio | Indica se il repository è stato ufficialmente archiviato dai maintainer | API GitHub (flag archived) | 3 |

### Qualità del Codice

| Parametro | Descrizione | Metodo di Misurazione | Peso (Esempio) |
|-----------|-------------|------------------------|----------------|
| Complessità Media | Misura oggettiva della difficoltà di comprensione/manutenzione del codice | Tool Analisi Statica (es. Radon, Lizard per Python; SonarQube, PMD per Java, etc.) | 3 |
| Aderenza Stile (Linting) | Consistenza e leggibilità del codice secondo standard definiti | Analisi file configurazione linter (.flake8, .eslintrc), Output CI, Esecuzione linter locale | 4 |
| Code Smells | Pattern noti che suggeriscono problemi strutturali o di design | Tool Analisi Statica | 3 |
| Commenti nel Codice | Presenza e (potenzialmente) utilità dei commenti per spiegare logiche complesse | Analisi Statica (densità), LLM (valutazione qualitativa/semantica) | 3 |

### Documentazione

| Parametro | Descrizione | Metodo di Misurazione | Peso (Esempio) |
|-----------|-------------|------------------------|----------------|
| README.md (Presenza/Qualità) | Chiarezza del punto di ingresso: scopo, installazione, uso base | API GitHub (presenza file), LLM (valutazione chiarezza, completezza, utilità) | 5 |
| Documentazione Estesa | Disponibilità di guide più approfondite (Wiki, /docs, sito esterno) | API GitHub (presenza file/wiki), LLM (valutazione struttura/copertura se accessibile) | 4 |
| File Standard (LICENSE) | Presenza e chiarezza della licenza d'uso | API GitHub (controllo esistenza file LICENSE/COPYING) | 5 |
| File Standard (CONTRIB/COC) | Presenza di linee guida per contribuire e codice di condotta | API GitHub (controllo esistenza file specifici: CONTRIBUTING.md, CODE_OF_CONDUCT.md) | 3 |
| Qualità Esempi d'Uso | Chiarezza e utilità degli esempi forniti per capire come usare il progetto | LLM (valutazione chiarezza e praticità), Analisi struttura repo (presenza cartella /examples) | 4 |

### Community & Collaborazione

| Parametro | Descrizione | Metodo di Misurazione | Peso (Esempio) |
|-----------|-------------|------------------------|----------------|
| Uso Issue/PR Templates | Facilitano contributi e segnalazioni strutturate | API GitHub (controllo file in .github/) | 3 |
| Uso GitHub Discussions | Utilizzo della piattaforma dedicata per discussioni più ampie | API GitHub (check disponibilità e attività sezione Discussions) | 2 |
| Tono/Costruttività Discussioni | Qualità delle interazioni tra utenti e mantenitori | LLM (Analisi sentiment/costruttività commenti Issues/PR) | 3 |
| Uso Label Issues | Organizzazione e categorizzazione efficace delle issues (bug, feature, etc.) | API GitHub (analisi label usate sulle issues) | 2 |

### Sicurezza

| Parametro | Descrizione | Metodo di Misurazione | Peso (Esempio) |
|-----------|-------------|------------------------|----------------|
| File SECURITY.md | Chiarezza su policy di sicurezza e reporting vulnerabilità | API GitHub (controllo esistenza file) | 4 |
| Uso GitHub Security Features | Utilizzo di Dependabot, Code Scanning, Secret Scanning | API GitHub (Alerts, check configurazione), Analisi file workflow CI | 4 |
| Dipendenze Aggiornate | Indica se le librerie/componenti esterni usati sono recenti (meno vulnerabilità note) | Analisi file dipendenze (requirements.txt, package.json, etc.) + Check versioni (script Python, API pkg) | 5 |

### Testing & CI/CD

| Parametro | Descrizione | Metodo di Misurazione | Peso (Esempio) |
|-----------|-------------|------------------------|----------------|
| Presenza Test Suite | Esistenza di test automatici per verificare la correttezza | Analisi struttura repo (presenza cartelle /tests, /spec, etc.) | 4 |
| Test Coverage | Percentuale di codice coperta dai test (indicatore di robustezza) | Tool Copertura (Coverage.py, JaCoCo), Badge nel README, Output CI (se accessibile) | 5 |
| Integrazione Continua (CI) | Automazione di build e test ad ogni modifica | Analisi file configurazione CI (.github/workflows, .travis.yml), Badge README, API GitHub Checks | 5 |
| Sicurezza in CI | Integrazione di tool di scansione sicurezza (SAST, DAST, SCA) nella pipeline CI | Analisi file configurazione CI (ricerca step specifici di security scan) | 4 |

### Setup & Usabilità

| Parametro | Descrizione | Metodo di Misurazione | Peso (Esempio) |
|-----------|-------------|------------------------|----------------|
| Facilità di Setup | Presenza di istruzioni chiare e complete per l'installazione e configurazione | LLM (valutazione chiarezza istruzioni), Analisi README e docs | 4 |

## Personalizzazione dei Pesi

I pesi indicati sono solo degli esempi e rappresentano una possibile valutazione soggettiva dell'importanza di ciascun parametro. È consigliabile adattare questi pesi in base allo scopo specifico del progetto di valutazione:

- **Ambiente Enterprise Critico**: Dare un peso molto più alto alla sicurezza, alla licenza e alla manutenzione rispetto alla popolarità.
- **Progetti Innovativi**: Dare più peso all'attività recente e alla qualità del codice.
- **Librerie di Base**: Dare più peso alla stabilità, test coverage e documentazione.

Per personalizzare i pesi, modificare il file `config.json` secondo le proprie esigenze.