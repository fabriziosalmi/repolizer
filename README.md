# Repolizer - Analizzatore di Repository GitHub

Repolizer è uno strumento per analizzare e valutare repository GitHub in base a diversi parametri di qualità, attività, manutenzione e impatto. Lo strumento utilizza le API di GitHub e strumenti di analisi statica per raccogliere dati e calcolare punteggi ponderati.

## Funzionalità

- Analisi completa di repository GitHub in base a parametri configurabili
- Calcolo di punteggi ponderati per valutare la qualità complessiva
- Visualizzazione interattiva dei risultati con grafici e tabelle
- Dashboard per confrontare più repository e visualizzare classifiche
- Suggerimenti specifici per migliorare la qualità del repository
- Personalizzazione dei pesi per adattare l'analisi alle proprie esigenze
- Esportazione dei report in formato HTML e JSON

## Parametri di Valutazione

Repolizer valuta i repository in base a diverse categorie di parametri:

- **Distribuzione** - Popolarità e impatto nella community
- **Manutenzione** - Frequenza e qualità degli aggiornamenti
- **Codice** - Qualità e manutenibilità del codice sorgente
- **Documentazione** - Completezza e chiarezza della documentazione
- **Collaborazione** - Gestione della community e dei contributi esterni
- **Sicurezza** - Pratiche di sicurezza e gestione delle vulnerabilità
- **Integrazione** - Testing, CI/CD e integrazione con altri strumenti
- **Adozione** - Livello di adozione e utilizzo del software nella comunità

Ogni parametro ha un peso configurabile per adattare l'analisi alle specifiche esigenze del progetto. Per una descrizione dettagliata dei parametri, consulta il file [docs/parametri.md](docs/parametri.md).

## Struttura dei Punteggi

I punteggi di Repolizer sono calcolati su una scala da 0 a 10:

- **8-10**: Eccellente - Il repository soddisfa completamente i criteri di qualità
- **6-7.9**: Buono - Il repository soddisfa la maggior parte dei criteri di qualità
- **4-5.9**: Sufficiente - Il repository soddisfa i criteri di base
- **0-3.9**: Insufficiente - Il repository necessita di miglioramenti significativi

## Architettura del Sistema

Repolizer è composto da diversi moduli che lavorano insieme:

- **repolizer.py** - Script principale per l'analisi di un singolo repository
- **batch_repolizer.py** - Analisi di più repository in modalità batch
- **scraper.py** - Identificazione di repository rilevanti basati su criteri geografici o altri criteri di ricerca
- **report_server.py** - Server web per visualizzare e confrontare i report generati
- **example.py** - Esempio di utilizzo programmatico della libreria

## Installazione

```bash
# Clona il repository
git clone https://github.com/fabriziosalmi/repolizer.git
cd repolizer

# Installa le dipendenze
pip install -r requirements.txt

# Configura il token GitHub (opzionale ma consigliato)
cp .env.example .env
# Modifica il file .env inserendo il tuo token GitHub
```

## Utilizzo

### Analisi di un Repository

```bash
python repolizer.py --repo username/repository
```

### Opzioni Disponibili

```bash
python repolizer.py --repo username/repository [--config config.json] [--output report.json] [--no-viz]
```

Parametri:
- `--repo`: Nome del repository da analizzare (obbligatorio)
- `--config`: Percorso del file di configurazione personalizzato (opzionale)
- `--output`: Percorso del file di output per il report JSON (opzionale)
- `--no-viz`: Disabilita la visualizzazione grafica dei risultati (opzionale)

### Analisi Batch di Repository

Per analizzare multipli repository in batch:

```bash
python batch_repolizer.py --file repos.txt
```

Parametri:
- `--file`: Il percorso al file contenente la lista dei repository (uno per riga)
- `--clone`: Clona i repository localmente per un'analisi più approfondita
- `--no-rich`: Disabilita l'output formattato (utile per i log)

Il processo genera:
- Report JSON e HTML per ogni repository
- Un riepilogo complessivo dell'analisi batch

### Ricerca di Repository Italiani

Per trovare repository GitHub sviluppati in Italia o da sviluppatori italiani:

```bash
python scraper.py [--query "query aggiuntiva"]
```

Parametri:
- `--query`: Query di ricerca aggiuntiva (es. "topic:ai location:milan")
- `--max-pages`: Numero massimo di pagine di risultati da recuperare per query
- `--workers`: Numero di worker concorrenti per l'elaborazione
- `--cache-hours`: Durata in ore per mantenere valide le voci della cache

I repository trovati vengono salvati in un file `repos.txt` che può essere usato direttamente per l'analisi batch.

## Visualizzazione dei Risultati

Repolizer offre diverse modalità di visualizzazione dei risultati:

1. **Report HTML individuali** - Report dettagliati per singolo repository
2. **Dashboard Comparativa** - Vista top 100 con confronto tra repository
3. **Grafici Radar** - Visualizzazione delle performance per categoria
4. **Grafici a Barre** - Confronto diretto dei punteggi per parametro

Per visualizzare i report:
```bash
# Avvia il server di visualizzazione dei report
python report_server.py
```
Quindi apri `http://localhost:8000` nel tuo browser per accedere all'interfaccia di visualizzazione.

## Esempi di Output

Ecco un esempio di grafico radar che mostra il punteggio per categoria:

## Personalizzazione

È possibile personalizzare i pesi dei parametri di valutazione modificando il file `config.json`. Esempio:

```json
{
  "parametri": {
    "sicurezza": {
      "dipendenze_aggiornate": {
        "descrizione": "Indica se le librerie/componenti esterni usati sono recenti",
        "metodo": "Analisi file dipendenze",
        "peso": 5
      }
    }
  }
}
```

Per una guida completa alla personalizzazione, consulta il file [docs/guida_utente.md](docs/guida_utente.md).

## Contributi

I contributi sono benvenuti! Per favore, consulta il file [CONTRIBUTING.md](CONTRIBUTING.md) per le linee guida su come contribuire al progetto.

## Licenza

Questo progetto è distribuito con licenza MIT. Vedi il file [LICENSE](LICENSE) per ulteriori dettagli.