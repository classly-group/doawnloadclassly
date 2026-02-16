import customtkinter as ctk
from tkinter import filedialog, messagebox
from backend_with_pdf import DatabaseManager, GenerateurPlan

class ClasslyApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Classly Pro")
        self.geometry("1100x750")
        self.db = DatabaseManager()
        self.gen = GenerateurPlan(self.db)
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="CLASSLY", font=("Arial", 24, "bold")).pack(pady=30)
        
        ctk.CTkButton(self.sidebar, text="Classes", command=self.show_classes).pack(pady=10, padx=10, fill="x")
        ctk.CTkButton(self.sidebar, text="Élèves", command=self.show_eleves).pack(pady=10, padx=10, fill="x")
        ctk.CTkButton(self.sidebar, text="Générateur", command=self.show_gen).pack(pady=10, padx=10, fill="x")
        
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.current_class_id = None
        self.show_classes()

    def clear(self):
        for w in self.main_frame.winfo_children(): w.destroy()

    def show_classes(self):
        self.clear()
        ctk.CTkLabel(self.main_frame, text="Gestion des Classes", font=("Arial", 22)).pack(pady=10)
        f = ctk.CTkFrame(self.main_frame); f.pack(pady=10)
        e = ctk.CTkEntry(f, placeholder_text="Nom de classe"); e.pack(side="left", padx=5)
        ctk.CTkButton(f, text="+", width=40, command=lambda: [self.db.add_class(e.get()), self.show_classes()]).pack(side="left")

        scroll = ctk.CTkScrollableFrame(self.main_frame); scroll.pack(fill="both", expand=True)
        for c in self.db.get_classes():
            r = ctk.CTkFrame(scroll); r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=c[1], width=150, anchor="w").pack(side="left", padx=10)
            ctk.CTkButton(r, text="Import Pronote", command=lambda i=c[0]: self.import_csv(i)).pack(side="right", padx=5)
            ctk.CTkButton(r, text="Élèves", command=lambda i=c[0]: self.go_eleves(i)).pack(side="right", padx=5)

    def import_csv(self, cid):
        p = filedialog.askopenfilename()
        if p:
            n = self.db.importer_csv_pronote(cid, p)
            messagebox.showinfo("Import", f"{n} élèves importés.")

    def go_eleves(self, cid):
        self.current_class_id = cid
        self.show_eleves()

    def show_eleves(self):
        self.clear()
        if not self.current_class_id: return
        eleves = self.db.get_eleves(self.current_class_id)
        ctk.CTkLabel(self.main_frame, text=f"Paramètres des élèves", font=("Arial", 22)).pack(pady=10)
        
        scroll = ctk.CTkScrollableFrame(self.main_frame); scroll.pack(fill="both", expand=True)
        for e in eleves:
            r = ctk.CTkFrame(scroll); r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=f"{e['nom']} {e['prenom']}", width=180, anchor="w").pack(side="left", padx=10)
            
            # Devant / Derrière
            cb_dev = ctk.CTkCheckBox(r, text="Devant", width=80, command=lambda i=e['id'], v=e['placer_devant']: [self.db.update_contrainte(i, 'placer_devant', 1-v), self.show_eleves()])
            if e['placer_devant']: cb_dev.select()
            cb_dev.pack(side="left")
            
            cb_der = ctk.CTkCheckBox(r, text="Derrière", width=80, command=lambda i=e['id'], v=e['placer_derriere']: [self.db.update_contrainte(i, 'placer_derriere', 1-v), self.show_eleves()])
            if e['placer_derriere']: cb_der.select()
            cb_der.pack(side="left")

            # Bouton Exclusions
            ctk.CTkButton(r, text="Ne pas placer à côté de...", width=160, fg_color="#555", command=lambda obj=e: self.open_exclusions(obj)).pack(side="right", padx=10)

    def open_exclusions(self, eleve):
        # Fenêtre Popup
        pop = ctk.CTkToplevel(self)
        pop.title(f"Exclusions pour {eleve['nom']}")
        pop.geometry("400x500")
        pop.attributes("-topmost", True)
        
        ctk.CTkLabel(pop, text=f"Éviter de placer {eleve['nom']} à côté de :", wraplength=350).pack(pady=10)
        
        scroll = ctk.CTkScrollableFrame(pop); scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        all_others = [e for e in self.db.get_eleves(self.current_class_id) if e['id'] != eleve['id']]
        current_excl = self.db.get_exclusions_ids(eleve['id'])
        
        for other in all_others:
            var = ctk.IntVar(value=1 if other['id'] in current_excl else 0)
            def toggle(oid=other['id'], v_var=var):
                action = "add" if v_var.get() == 1 else "delete"
                self.db.manage_exclusion(self.current_class_id, eleve['id'], oid, action)
            
            cb = ctk.CTkCheckBox(scroll, text=f"{other['nom']} {other['prenom']}", variable=var, command=toggle)
            cb.pack(fill="x", pady=2)

    def show_gen(self):
        self.clear()
        ctk.CTkLabel(self.main_frame, text="Configuration du Plan", font=("Arial", 22)).pack(pady=10)
        
        classes = self.db.get_classes()
        if not classes: return
        
        class_map = {c[1]: c[0] for c in classes}
        sel_c = ctk.CTkOptionMenu(self.main_frame, values=list(class_map.keys())); sel_c.pack(pady=10)
        
        f = ctk.CTkFrame(self.main_frame); f.pack(pady=10, fill="x")
        ctk.CTkLabel(f, text="Colonnes :").grid(row=0, column=0, padx=10)
        e_col = ctk.CTkEntry(f, width=50); e_col.insert(0, "4"); e_col.grid(row=0, column=1)
        
        ctk.CTkLabel(f, text="Lignes :").grid(row=0, column=2, padx=10)
        e_row = ctk.CTkEntry(f, width=50); e_row.insert(0, "5"); e_row.grid(row=0, column=3)
        
        ctk.CTkLabel(f, text="Places/table :").grid(row=0, column=4, padx=10)
        e_plc = ctk.CTkOptionMenu(f, values=["1", "2", "3"], width=60); e_plc.set("2"); e_plc.grid(row=0, column=5)

        def run():
            cid = class_map[sel_c.get()]
            plan = self.gen.generer(cid, int(e_row.get()), int(e_col.get()), int(e_plc.get()))
            path = filedialog.asksaveasfilename(defaultextension=".pdf")
            if path:
                self.gen.exporter_pdf(plan, path, sel_c.get(), int(e_row.get()), int(e_col.get()))
                messagebox.showinfo("OK", "Plan généré !")

        ctk.CTkButton(self.main_frame, text="GÉNÉRER PDF", command=run, height=50, fg_color="green").pack(pady=20)

if __name__ == "__main__":
    app = ClasslyApp()
    app.mainloop()
