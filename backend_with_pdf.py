import sqlite3
import csv
import random
import re
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors

DB_NAME = "classly_data.db"

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute('''CREATE TABLE IF NOT EXISTS classes (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            nom TEXT UNIQUE)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS eleves (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            class_id INTEGER,
                            nom TEXT, prenom TEXT, sexe TEXT,
                            placer_devant INTEGER DEFAULT 0,
                            placer_derriere INTEGER DEFAULT 0,
                            FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS exclusions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            class_id INTEGER,
                            eleve_1_id INTEGER, eleve_2_id INTEGER,
                            FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE)''')
        self.conn.commit()

    def importer_csv_pronote(self, class_id, filepath):
        count = 0
        try:
            with open(filepath, newline='', encoding='utf-8-sig') as csvfile:
                content = csvfile.read(2048)
                csvfile.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(content, delimiters=[',', ';'])
                except:
                    dialect = csv.excel
                reader = csv.DictReader(csvfile, dialect=dialect)
                cursor = self.conn.cursor()
                for row in reader:
                    row = {k.strip(): v for k, v in row.items() if k}
                    nom_complet = (row.get('Élèves') or row.get('élèves') or row.get('Eleves') or '').strip()
                    if nom_complet:
                        match = re.match(r"^([A-Z\s\-']+[A-Z])\s+([A-Z][a-z].*)", nom_complet)
                        nom, prenom = (match.group(1).upper(), match.group(2)) if match else (nom_complet.upper(), "")
                        cursor.execute("INSERT INTO eleves (class_id, nom, prenom, sexe) VALUES (?, ?, ?, ?)",
                                       (class_id, nom.strip(), prenom.strip(), "M"))
                        count += 1
                self.conn.commit()
        except Exception as e:
            print(f"Erreur import : {e}")
            return 0
        return count

    def get_classes(self):
        c = self.conn.cursor(); c.execute("SELECT * FROM classes"); return c.fetchall()

    def add_class(self, nom):
        try:
            self.conn.cursor().execute("INSERT INTO classes (nom) VALUES (?)", (nom,))
            self.conn.commit(); return True
        except: return False

    def delete_class(self, cid):
        self.conn.cursor().execute("DELETE FROM classes WHERE id = ?", (cid,)); self.conn.commit()

    def get_eleves(self, cid):
        self.conn.row_factory = sqlite3.Row
        c = self.conn.cursor(); c.execute("SELECT * FROM eleves WHERE class_id = ? ORDER BY nom ASC", (cid,))
        return [dict(r) for r in c.fetchall()]

    def update_contrainte(self, eid, champ, val):
        cursor = self.conn.cursor()
        # Si on place devant, on ne peut pas être derrière et inversement
        if champ == 'placer_devant' and val == 1:
            cursor.execute("UPDATE eleves SET placer_devant=1, placer_derriere=0 WHERE id=?", (eid,))
        elif champ == 'placer_derriere' and val == 1:
            cursor.execute("UPDATE eleves SET placer_devant=0, placer_derriere=1 WHERE id=?", (eid,))
        else:
            cursor.execute(f"UPDATE eleves SET {champ} = ? WHERE id = ?", (val, eid))
        self.conn.commit()

    def manage_exclusion(self, cid, id1, id2, action="add"):
        c = self.conn.cursor()
        low, high = min(id1, id2), max(id1, id2)
        if action == "add":
            c.execute("INSERT OR IGNORE INTO exclusions (class_id, eleve_1_id, eleve_2_id) VALUES (?,?,?)", (cid, low, high))
        else:
            c.execute("DELETE FROM exclusions WHERE class_id=? AND eleve_1_id=? AND eleve_2_id=?", (cid, low, high))
        self.conn.commit()

    def get_exclusions_ids(self, eid):
        c = self.conn.cursor()
        c.execute("SELECT eleve_1_id, eleve_2_id FROM exclusions WHERE eleve_1_id=? OR eleve_2_id=?", (eid, eid))
        return {r[0] if r[1] == eid else r[1] for r in c.fetchall()}

class GenerateurPlan:
    def __init__(self, db):
        self.db = db

    def generer(self, class_id, nb_rows, nb_cols, places_par_table):
        eleves = self.db.get_eleves(class_id)
        
        # Séparation par priorité
        devant = [e for e in eleves if e['placer_devant']]
        derriere = [e for e in eleves if e['placer_derriere']]
        autres = [e for e in eleves if not e['placer_devant'] and not e['placer_derriere']]
        
        random.shuffle(devant)
        random.shuffle(autres)
        random.shuffle(derriere)
        
        liste_triee = devant + autres + derriere
        
        nb_tables = nb_rows * nb_cols
        plan = [[None for _ in range(places_par_table)] for _ in range(nb_tables)]
        
        idx = 0
        for t in range(nb_tables):
            for p in range(places_par_table):
                if idx < len(liste_triee):
                    plan[t][p] = liste_triee[idx]
                    idx += 1
        return plan

    def exporter_pdf(self, plan, filename, class_nom, nb_rows, nb_cols):
        c = canvas.Canvas(filename, pagesize=landscape(A4))
        w_p, h_p = landscape(A4)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(w_p/2, h_p - 1.5*cm, f"PLAN DE CLASSE : {class_nom}")
        
        # Grille
        m_x, m_y = 1.5*cm, 2.5*cm
        cell_w = (w_p - 2*m_x) / nb_cols
        cell_h = (h_p - m_y - 1*cm) / nb_rows
        
        for r in range(nb_rows):
            for col in range(nb_cols):
                t_idx = r * nb_cols + col
                if t_idx < len(plan):
                    x = m_x + (col * cell_w) + cell_w*0.05
                    y = h_p - m_y - ((r + 1) * cell_h) + cell_h*0.05
                    t_w, t_h = cell_w*0.9, cell_h*0.8
                    
                    c.setStrokeColor(colors.black)
                    c.roundRect(x, y, t_w, t_h, 4)
                    
                    table_data = plan[t_idx]
                    if table_data:
                        slot_w = t_w / len(table_data)
                        for i, e in enumerate(table_data):
                            if e:
                                ex = x + (i * slot_w) + slot_w/2
                                ey = y + t_h/2
                                c.setFont("Helvetica-Bold", 8)
                                # Couleur selon contrainte
                                if e['placer_devant']: c.setFillColor(colors.green)
                                elif e['placer_derriere']: c.setFillColor(colors.blue)
                                else: c.setFillColor(colors.black)
                                
                                c.drawCentredString(ex, ey+4, e['nom'][:12])
                                c.setFont("Helvetica", 7)
                                c.drawCentredString(ex, ey-6, e['prenom'][:12])
        c.save()
