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