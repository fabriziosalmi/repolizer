import json
import sqlite3
import os
from datetime import datetime
import glob


def create_connection(db_file):
    """Creates a database connection to the SQLite database specified by db_file."""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except sqlite3.Error as e:
        print(e)

    return conn


def create_tables(conn):
    """Creates tables for the data if they don't exist."""
    try:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                nome_repository TEXT PRIMARY KEY,
                url TEXT,
                data_analisi DATETIME,
                punteggio_totale REAL,
                valutazione_qualitativa TEXT,
                bandit_issues INTEGER,
                high_severity INTEGER,
                medium_severity INTEGER,
                low_severity INTEGER,
                issue_density REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS punteggi (
                nome_repository TEXT,
                distribuzione REAL,
                manutenzione REAL,
                codice REAL,
                documentazione REAL,
                collaborazione REAL,
                sicurezza REAL,
                integrazione REAL,
                adozione REAL,
                FOREIGN KEY (nome_repository) REFERENCES reports (nome_repository)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dettagli (
                nome_repository TEXT,
                categoria TEXT,
                sotto_categoria TEXT,
                valore TEXT,
                punteggio REAL,
                peso INTEGER,
                descrizione TEXT,
                conta_punteggio BOOLEAN,
                score_is_na BOOLEAN,
                FOREIGN KEY (nome_repository) REFERENCES reports (nome_repository)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suggerimenti (
                nome_repository TEXT,
                categoria TEXT,
                suggerimento TEXT,
                FOREIGN KEY (nome_repository) REFERENCES reports (nome_repository)
            )
        """)

        conn.commit()
    except sqlite3.Error as e:
        print(f"Error creating tables: {e}")


def insert_or_update_report(conn, report_data):
    """
    Inserts or updates report data into the SQLite database.
    Handles missing 'score_is_na' key and boolean conversion.
    """

    repo_name = report_data['nome_repository']
    analysis_date = datetime.strptime(report_data['data_analisi'], '%Y-%m-%d %H:%M:%S')

    cursor = conn.cursor()

    # Check if a report with the same nome_repository already exists
    cursor.execute("SELECT data_analisi FROM reports WHERE nome_repository = ?", (repo_name,))
    existing_report = cursor.fetchone()

    if existing_report:
        existing_date = datetime.strptime(existing_report[0], '%Y-%m-%d %H:%M:%S')

        # If the existing report is more recent, skip the insertion
        if existing_date >= analysis_date:
            print(f"Skipping update for {repo_name}: existing report is more recent.")
            return

        # If the existing report is older, delete the existing report and its associated data
        print(f"Updating report for {repo_name}: new report is more recent.")
        delete_report(conn, repo_name)
    else:
        print(f"Inserting new report for {repo_name}.")

    # Insert the report data
    try:

        cursor.execute("""
            INSERT INTO reports (nome_repository, url, data_analisi, punteggio_totale,
                                 valutazione_qualitativa, bandit_issues, high_severity,
                                 medium_severity, low_severity, issue_density)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report_data['nome_repository'],
            report_data['url'],
            report_data['data_analisi'],
            report_data['punteggio_totale'],
            report_data['valutazione_qualitativa'],
            report_data['dettagli_sicurezza']['bandit_issues'],
            report_data['dettagli_sicurezza']['high_severity'],
            report_data['dettagli_sicurezza']['medium_severity'],
            report_data['dettagli_sicurezza']['low_severity'],
            report_data['dettagli_sicurezza']['issue_density']
        ))

        # Insert punteggi data
        punteggi = report_data['punteggi']
        cursor.execute("""
            INSERT INTO punteggi (nome_repository, distribuzione, manutenzione, codice,
                                  documentazione, collaborazione, sicurezza, integrazione, adozione)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report_data['nome_repository'],
            punteggi['distribuzione'],
            punteggi['manutenzione'],
            punteggi['codice'],
            punteggi['documentazione'],
            punteggi['collaborazione'],
            punteggi['sicurezza'],
            punteggi['integrazione'],
            punteggi['adozione']
        ))

        # Insert dettagli data
        for categoria, dettagli_categoria in report_data['dettagli'].items():
            for sotto_categoria, dettaglio in dettagli_categoria.items():
                # Handle missing 'score_is_na' key using get() with a default value
                conta_punteggio = 1 if dettaglio.get('conta_punteggio', False) else 0  # Default to False if missing
                score_is_na = 1 if dettaglio.get('score_is_na', False) else 0  # Default to False if missing

                cursor.execute("""
                    INSERT INTO dettagli (nome_repository, categoria, sotto_categoria, valore,
                                          punteggio, peso, descrizione, conta_punteggio, score_is_na)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report_data['nome_repository'],
                    categoria,
                    sotto_categoria,
                    dettaglio['valore'],
                    dettaglio['punteggio'],
                    dettaglio['peso'],
                    dettaglio['descrizione'],
                    conta_punteggio,
                    score_is_na
                ))

        # Insert suggerimenti data
        for categoria, lista_suggerimenti in report_data['suggerimenti'].items():
            for suggerimento in lista_suggerimenti:
                cursor.execute("""
                    INSERT INTO suggerimenti (nome_repository, categoria, suggerimento)
                    VALUES (?, ?, ?)
                """, (
                    report_data['nome_repository'],
                    categoria,
                    suggerimento
                ))

        conn.commit()
        print(f"Successfully inserted/updated data for {report_data['nome_repository']}.")

    except sqlite3.Error as e:
        print(f"Error inserting/updating data for {report_data['nome_repository']}: {e}")
        conn.rollback()


def delete_report(conn, repo_name):
    """Deletes a report and its associated data from the database."""
    cursor = conn.cursor()

    try:
        # Delete data from child tables first due to foreign key constraints
        cursor.execute("DELETE FROM punteggi WHERE nome_repository = ?", (repo_name,))
        cursor.execute("DELETE FROM dettagli WHERE nome_repository = ?", (repo_name,))
        cursor.execute("DELETE FROM suggerimenti WHERE nome_repository = ?", (repo_name,))

        # Delete the report from the reports table
        cursor.execute("DELETE FROM reports WHERE nome_repository = ?", (repo_name,))

        conn.commit()
        print(f"Successfully deleted data for {repo_name}.")

    except sqlite3.Error as e:
        print(f"Error deleting data for {repo_name}: {e}")
        conn.rollback()


def process_reports(db_file, reports_folder):
    """
    Processes all JSON report files in the specified folder and saves them to the SQLite database.
    """
    conn = create_connection(db_file)
    if conn is None:
        print("Failed to connect to the database.")
        return

    create_tables(conn)

    # Use glob to find all json files in the reports folder
    report_files = glob.glob(os.path.join(reports_folder, "*.json"))

    if not report_files:
        print(f"No JSON report files found in '{reports_folder}'.")
        return

    for report_file in report_files:
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
                insert_or_update_report(conn, report_data)
        except FileNotFoundError:
            print(f"Error: File not found: {report_file}")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON in {report_file}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while processing {report_file}: {e}")

    conn.close()


# Example Usage:
if __name__ == "__main__":
    db_file = "reports.db"  # Replace with your desired database file
    reports_folder = "reports"  # Replace with your folder containing the JSON reports
    process_reports(db_file, reports_folder)
    print("Report processing complete.")