# Guida Utente di Repolizer

Questa guida fornisce istruzioni dettagliate su come installare, configurare e utilizzare Repolizer per analizzare repository GitHub.

## Installazione

### Prerequisiti

- Python 3.7 o superiore
- Pip (gestore pacchetti Python)
- Git (opzionale, per clonare il repository)

### Passaggi di Installazione

1. Clona il repository o scarica i file:

   ```bash
   git clone https://github.com/yourusername/repolizer.git
   cd repolizer
   ```

2. Installa le dipendenze:

   ```bash
   pip install -r requirements.txt
   ```

3. Configura il token GitHub (opzionale ma consigliato):
   - Crea un token di accesso personale su GitHub: [https://github.com/settings/tokens](https://github.com/settings/tokens)
   - Copia il file `.env.example` in `.env`:
     ```bash
     cp .env.example .env
     ```
   - Modifica il file `.env` inserendo il tuo token:
     ```
     GITHUB_TOKEN=your_personal_access_token
     ```

## Utilizzo Base

### Analizzare un Repository

Per analizzare un repository GitHub, esegui il comando:

```bash
python repolizer.py --repo username/repository
```

Esempio:

```bash
python repolizer.py --repo tensorflow/tensorflow
```

### Opzioni Disponibili

- `--repo`: Nome del repository da analizzare (obbligatorio)
- `--config`: Percorso del file di configurazione personalizzato (opzionale)
- `--output`: Percorso del file di output per il report JSON (opzionale)
- `--no-viz`: Disabilita la visualizzazione grafica dei risultati (opzionale)

Esempio con tutte le opzioni:

```bash
python repolizer.py --repo tensorflow/tensorflow --config config_personalizzato.json --output report_tensorflow.json --no-viz
```

## Personalizzazione

### Modificare i Pesi dei Parametri

Per personalizzare i pesi dei parametri di valutazione, modifica il file `config.json`. Ogni parametro ha un peso configurabile da 1 a 5:

- **1**: Importanza Bassa
- **2**: Importanza Media-Bassa
- **3**: Importanza Media
- **4**: Importanza Alta
- **5**: Importanza Altissima

Esempio di modifica del peso di un parametro:

```json
{
  "parametri": {
    "sicurezza": {
      "dipendenze_aggiornate": {
        "descrizione": "Indica se le librerie/componenti esterni usati sono recenti",
        "metodo": "Analisi file dipendenze",
        "peso": 5  // Modifica questo valore secondo le tue esigenze
      }
    }
  }
}
```

### Creare una Configurazione Personalizzata

Puoi creare un file di configurazione personalizzato copiando e modificando il file `config.json` predefinito:

```bash
cp config.json config_personalizzato.json
```

Modifica il nuovo file secondo le tue esigenze e utilizzalo con l'opzione `--config`.

## Interpretazione dei Risultati

### Report Testuale

Il report testuale mostra:

- Informazioni generali sul repository
- Punteggio totale (su una scala da 0 a 10)
- Punteggi per categoria
- Dettagli per ogni parametro analizzato

### Visualizzazione Grafica

La visualizzazione grafica mostra un grafico a barre con i punteggi per ogni categoria, ordinati dal più basso al più alto. Una linea rossa tratteggiata indica il punteggio totale.

### File JSON

Se specifichi un file di output con l'opzione `--output`, i risultati completi dell'analisi vengono salvati in formato JSON. Questo file può essere utilizzato per ulteriori analisi o per l'integrazione con altri strumenti.

## Utilizzo Programmatico

Puoi utilizzare Repolizer come libreria Python nei tuoi script:

```python
from repolizer import RepoAnalyzer

# Crea un'istanza dell'analizzatore
analyzer = RepoAnalyzer("username/repository")

# Esegue l'analisi
results = analyzer.analyze()

# Accedi ai risultati
print(f"Punteggio totale: {results['punteggio_totale']}")

# Genera il report
analyzer.generate_report("report.json")

# Visualizza i risultati
analyzer.visualize_results()
```

Vedi il file `example.py` per un esempio completo di utilizzo programmatico.

## Risoluzione dei Problemi

### Limiti API GitHub

Se non utilizzi un token GitHub, potresti raggiungere rapidamente i limiti delle API. In questo caso, vedrai un messaggio di errore. Soluzioni:

1. Configura un token GitHub come descritto nella sezione Installazione
2. Attendi che il limite si resetti (solitamente dopo un'ora)

### Errori di Connessione

Se riscontri errori di connessione, verifica:

1. La tua connessione internet
2. Che il repository specificato esista e sia accessibile
3. Che il tuo token GitHub sia valido e abbia i permessi necessari

## Esempi di Casi d'Uso

### Valutazione di Dipendenze per Progetti Enterprise

Per valutare repository da utilizzare come dipendenze in un ambiente enterprise:

1. Modifica `config.json` aumentando i pesi di sicurezza, manutenzione e licenza
2. Esegui l'analisi sui repository candidati
3. Confronta i punteggi totali e i punteggi nelle categorie critiche

### Confronto tra Alternative

Per confrontare repository alternativi che offrono funzionalità simili:

1. Analizza ciascun repository
2. Salva i report in file JSON separati
3. Utilizza uno script personalizzato per confrontare i risultati o visualizzarli insieme

## Contribuire al Progetto

Se desideri contribuire a Repolizer, puoi:

1. Segnalare bug o suggerire miglioramenti tramite le issues
2. Proporre nuovi parametri di valutazione
3. Migliorare la documentazione
4. Inviare pull request con nuove funzionalità o correzioni