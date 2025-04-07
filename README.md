# Repolizer - Analizzatore di Repository GitHub

Repolizer è uno strumento per analizzare e valutare repository GitHub in base a diversi parametri di qualità, attività, manutenzione e impatto. Lo strumento utilizza le API di GitHub e strumenti di analisi statica per raccogliere dati e calcolare punteggi ponderati.

## Funzionalità

- Analisi di repository GitHub in base a parametri configurabili
- Calcolo di punteggi ponderati per valutare la qualità complessiva
- Visualizzazione dei risultati in formato facilmente comprensibile
- Personalizzazione dei pesi per adattare l'analisi alle proprie esigenze

## Parametri di Valutazione

Repolizer valuta i repository in base a diverse categorie di parametri:

- Popolarità & Impatto
- Attività & Manutenzione
- Qualità del Codice
- Documentazione
- Community & Collaborazione
- Sicurezza
- Testing & CI/CD
- Setup & Usabilità

Ogni parametro ha un peso configurabile per adattare l'analisi alle specifiche esigenze del progetto.

## Installazione

```bash
# Clona il repository
git clone https://github.com/yourusername/repolizer.git
cd repolizer

# Installa le dipendenze
pip install -r requirements.txt
```

## Utilizzo

```bash
python repolizer.py --repo username/repository [--config config.json]
```

## Configurazione

È possibile personalizzare i pesi dei parametri di valutazione modificando il file `config.json`.

## Licenza

MIT