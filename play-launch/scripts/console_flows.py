"""Play Console flows with no API, run in the dedicated browser from the APPROVED expediente (stage 3).
Recorded on Keyboard & Mouse, 2026-11-15, console in Spanish (Latin America). Every answer comes from the
expediente: nothing is decided here, so stage 3 never stops for a question (the only stop is the key password).

    python console_flows.py all            --app <folder>   everything below, in order
    python console_flows.py declarations   --app <folder>   App content: privacy, ads, access, ad ID, government,
                                                            finance, health, content rating (IARC), audience, FGS
    python console_flows.py store-settings --app <folder>   category and contact details
    python console_flows.py listing        --app <folder>   default listing: languages, texts, icon, feature graphic,
                                                            screenshots one by one (keeps the order), AI asset labels
    python console_flows.py closed-test    --app <folder>   testers list and countries of "Prueba cerrada - Alpha"
    python console_flows.py release-notes  --app <folder>   notes of every language on the draft closed release
    python console_flows.py send-review    --app <folder>   send the pending changes for review (approval required)
    python console_flows.py pending        --app <folder>   which App content declarations still need attention

Before: create_app, bind-app, app signing (PEPK) and the first AAB (play.py release --track internal), then
`play.py promote --from internal --to alpha --draft --yes`. The data safety form goes by API (play.py data-safety).
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import console  # noqa: E402
import launch  # noqa: E402

# Labels of the Spanish (Latin America) console. Another console language needs its own table.
CATEGORY_ES = {"TOOLS": "Herramientas", "PRODUCTIVITY": "Productividad", "COMMUNICATION": "Comunicación",
               "EDUCATION": "Educación", "ENTERTAINMENT": "Entretenimiento", "LIFESTYLE": "Estilo de vida",
               "BOOKS_AND_REFERENCE": "Libros y referencias", "MUSIC_AND_AUDIO": "Música y audio",
               "PERSONALIZATION": "Personalización", "PHOTOGRAPHY": "Fotografía", "BUSINESS": "Negocios"}
LANG_ES = {"en-US": "Inglés (Estados Unidos), en-US", "es-419": "Español (Latinoamérica), es-419",
           "es-ES": "Español (España), es-ES", "pt-BR": "Portugués (Brasil), pt-BR"}
FGS_ES = {"CONNECTED_DEVICE": "Transferencia de datos continua a un dispositivo externo"}
AUDIENCE_ES = {"5 and under": "Menores de 5 años", "6-8": "6-8", "9-12": "9-12", "13-15": "13-15",
               "16-17": "16-17", "18 and over": "Mayores de 18 años"}
IMAGE_SLOTS = {"icon": "Ícono de la app", "featureGraphic": "Gráfico de funciones",
               "phoneScreenshots": "Capturas de pantalla de teléfono"}


class Flow:
    def __init__(self, folder):
        self.app = launch.App(folder)
        self.exp = self.app.expediente()
        st = self.app.state()
        self.app_id = st.get("console_app_id") or launch.fail("No console app id: console.py bind-app")
        profile = self.app.meta["profiles"]["play"]
        self.dev = console.profile_cfg(profile).get("developer_id") or launch.fail("console.py bind first")
        self.s = console.Session(profile)
        self.p = self.s.page
        self.out = console.evidence_dir(self.app)
        if self.s.developer_id() != self.dev:
            launch.fail("Wrong developer account in the browser: nothing done")

    # --- helpers ---------------------------------------------------------------------------------------
    def go(self, path):
        self.p.goto(f"{console.CONSOLE}/u/0/developers/{self.dev}/app/{self.app_id}/{path}", wait_until="domcontentloaded")
        console.settle(self.p)

    def shot(self, name):
        png, _ = console.snapshot(self.p, self.out, name)
        print(f"  evidence: {png}")

    def close_dialogs(self):
        for name in ("Ahora no", "Cerrar"):
            try:
                self.p.get_by_role("button", name=name).first.click(timeout=1500)
            except Exception:
                pass

    def click(self, role, name, exact=True, last=False):
        loc = self.p.get_by_role(role, name=name, exact=exact)
        (loc.last if last else loc.first).click()
        self.p.wait_for_timeout(1500)

    def save(self, name="Guardar"):
        console.dismiss_survey(self.p)
        self.p.get_by_role("button", name=name, exact=True).last.click()
        self.p.wait_for_timeout(5000)
        self.close_dialogs()

    def decl(self, key):
        d = self.exp["declarations"][key]
        if d.get("status") not in ("derived", "answered"):
            launch.fail(f"Declaration '{key}' is not answered in the approved expediente")
        return d["value"]

    def open_declaration(self, name):
        self.go("app-content/overview")
        btn = self.p.get_by_role("button", name=f"Comenzar la declaración de {name}")
        if btn.count():
            btn.first.click()
        else:
            card = self.p.locator(f"xpath=//*[normalize-space(text())='{name}']/following::*[normalize-space(text())='Editar declaración'][1]")
            if not card.count():
                print(f"  {name}: already complete")
                return False
            card.first.click()
        console.settle(self.p)
        return True

    # --- App content -----------------------------------------------------------------------------------
    def declarations(self):
        if self.open_declaration("Política de Privacidad"):
            self.p.get_by_role("textbox", name="URL de la política de privacidad").fill(self.exp["privacy_url"])
            self.save(); self.shot("decl-privacy")
        if self.open_declaration("Anuncios"):
            ads = self.decl("ads")
            self.click("radio", "Sí, mi app contiene anuncios" if ads else "No, mi app no contiene anuncios")
            self.save(); self.shot("decl-ads")
        if self.open_declaration("Detalles de acceso"):
            restricted = self.decl("app_access") not in (False, None) and "without special access" not in str(self.decl("app_access"))
            if restricted:
                launch.fail("App access with restrictions: needs reviewer instructions (record that path first)")
            self.click("radio", "No"); self.save(); self.shot("decl-access")
        if self.open_declaration("ID de publicidad"):
            self.click("radio", "Sí" if self.decl("advertising_id") else "No"); self.save(); self.shot("decl-adid")
        if self.open_declaration("Apps gubernamentales"):
            self.click("radio", "No" if str(self.decl("government_app")).lower() in ("no", "false") else "Sí")
            self.save(); self.shot("decl-gov")
        if self.open_declaration("Funciones financieras"):
            if str(self.decl("financial_features")).lower() not in ("none", "no", "false"):
                launch.fail("Financial features declared: record that path first")
            self.p.get_by_role("checkbox", name="Mi app no ofrece ninguna función financiera").check()
            self.click("button", "Siguiente", last=True); self.save(); self.shot("decl-finance")
        if self.open_declaration("Apps de salud"):
            if str(self.decl("health_apps")).lower() not in ("none", "no", "false"):
                launch.fail("Health features declared: record that path first")
            self.p.get_by_role("checkbox", name="Ninguna función de salud").check()
            self.click("button", "Siguiente", last=True); self.save(); self.shot("decl-health")
        if self.open_declaration("Clasificación del contenido"):
            self.content_rating()
        if self.open_declaration("Público objetivo y contenido"):
            groups = self.decl("target_audience")["age_groups"]
            for g in groups:
                self.p.get_by_role("checkbox", name=AUDIENCE_ES[g]).check()
            if any(g != "18 and over" for g in groups):
                launch.fail("Audience includes minors: the following steps (appeal to children, Families) are not recorded")
            self.click("button", "Siguiente", last=True); self.save(); self.shot("decl-audience")
        if self.open_declaration("Permisos de servicios en primer plano"):
            for fgs in self.decl("foreground_services") or []:
                label = FGS_ES.get(fgs) or launch.fail(f"No console label for foreground service {fgs}")
                self.p.get_by_role("checkbox", name=label).check(); self.p.wait_for_timeout(1000)
                video = self.exp["videos"].get(f"fgs_{fgs}") or launch.fail(f"No video for {fgs}")
                self.p.get_by_role("textbox", name="Vínculo de video").last.fill(video)
            self.save(); self.shot("decl-fgs")
        self.pending()

    def content_rating(self):
        cr = self.decl("content_rating")
        if any(v for k, v in cr.items() if k != "category"):
            launch.fail("Content rating with any 'yes' answer: record those questions first")
        self.click("button", "Responder el cuestionario")
        box = [b for b in self.p.locator("input[type=email], input[type=text]").all() if b.is_visible()]
        box[-1].fill(self.exp.get("iarc_email") or self.exp["contact"]["email"])
        self.p.get_by_role("radio", name="El resto de los tipos de app").check()
        self.p.get_by_role("checkbox", name="Acepto las Condiciones de Uso", exact=False).check()
        self.click("button", "Siguiente", last=True)
        console.settle(self.p)
        for _ in range(40):   # sections open one after another as questions are answered
            todo = None
            for g in self.p.get_by_role("radiogroup").all():
                radios = g.get_by_role("radio")
                if g.is_visible() and radios.count() and not any(r.is_checked() for r in radios.all()):
                    todo = g
                    break
            if todo is None:
                break
            todo.get_by_role("radio", name="No").check()
            self.p.wait_for_timeout(1200)
        self.save()
        self.click("button", "Siguiente", last=True)
        console.settle(self.p)
        self.shot("decl-rating-summary")
        self.save()

    def pending(self):
        self.go("app-content/overview")
        t = self.p.locator("body").inner_text()
        m = re.search(r"(\d+) declaraci\S+ requiere\S* atenci\S+", t)
        print("  App content:", m.group(0) if m else "all declarations complete")

    # --- Store settings --------------------------------------------------------------------------------
    def store_settings(self):
        self.go("store-settings")
        self.p.get_by_role("button", name="editar").first.click(); self.p.wait_for_timeout(2000)
        self.p.get_by_role("button", name="Categoría Campo obligatorio", exact=False).click(); self.p.wait_for_timeout(1000)
        self.p.get_by_role("option", name=CATEGORY_ES[self.exp["category"]], exact=True).click()
        self.p.get_by_role("dialog").last.get_by_role("button", name="Guardar").click(); self.p.wait_for_timeout(4000)
        self.close_dialogs()
        self.p.keyboard.press("Escape")
        self.p.get_by_role("button", name="editar").nth(1).click(); self.p.wait_for_timeout(2000)
        d = [x for x in self.p.get_by_role("dialog").all() if x.is_visible()][-1]
        boxes = d.get_by_role("textbox")
        boxes.nth(0).click(); boxes.nth(0).press("Control+a"); boxes.nth(0).press_sequentially(self.exp["contact"]["email"], delay=30)
        if self.exp["contact"].get("phone"):
            boxes.nth(1).click(); boxes.nth(1).press_sequentially(self.exp["contact"]["phone"], delay=30)
        boxes.nth(2).click(); boxes.nth(2).press("Control+a"); boxes.nth(2).press_sequentially(self.exp["contact"]["website"], delay=30)
        d.get_by_role("button", name="Guardar y publicar").click(); self.p.wait_for_timeout(3000)
        confirm = self.p.get_by_role("dialog", name="¿Quieres publicar el cambio en Google Play?", exact=False)
        if confirm.count():   # the app is still a draft: this only applies to the listing
            confirm.get_by_role("button", name="Guardar y publicar").click(); self.p.wait_for_timeout(5000)
        self.p.reload(wait_until="domcontentloaded"); console.settle(self.p)
        t = self.p.locator("body").inner_text()
        ok = self.exp["contact"]["email"] in t and CATEGORY_ES[self.exp["category"]] in t
        print("  store settings:", "OK" if ok else "CHECK (values not shown)")
        self.shot("store-settings")

    # --- Listing ---------------------------------------------------------------------------------------
    def section_count(self, label):
        sec = self.p.locator(f"xpath=//*[normalize-space(text())='{label}']/ancestor::*[.//*[normalize-space(text())='Agregar recursos']][1]")
        m = re.search(r"(\d+)/(\d+)", sec.first.inner_text())
        return int(m.group(1)) if m else 0

    def upload(self, label, file):
        before = self.section_count(label)
        self.p.locator(f"xpath=//*[normalize-space(text())='{label}']/following::*[normalize-space(text())='Agregar recursos'][1]").first.click()
        self.p.wait_for_timeout(2000)
        with self.p.expect_file_chooser(timeout=20000) as fc:
            self.p.get_by_role("button", name="Subir").click()
        fc.value.set_files(str(file))
        for _ in range(60):
            self.p.wait_for_timeout(1000)
            if self.section_count(label) > before:
                return
        launch.fail(f"Upload of {file.name} to '{label}' did not finish")

    def select_language(self, lang):
        cur = self.p.locator("xpath=//*[normalize-space(text())='Selecciona un idioma para editar']/following::button[1]").first
        if lang in cur.inner_text():
            return
        cur.click(); self.p.wait_for_timeout(1500)
        opt = self.p.get_by_text(LANG_ES[lang], exact=True)
        if not opt.count():   # not added yet: Administrar idiomas
            self.p.get_by_role("menuitem", name="Administrar idiomas").click(); self.p.wait_for_timeout(2500)
            d = [x for x in self.p.get_by_role("dialog").all() if x.is_visible()][-1]
            d.get_by_text(LANG_ES[lang], exact=True).click(); self.p.wait_for_timeout(1000)
            for name in ("Aplicar", "Guardar", "Listo", "Actualizar"):
                b = d.get_by_role("button", name=name)
                if b.count() and b.first.is_enabled():
                    b.first.click(); break
            console.settle(self.p)
            cur = self.p.locator("xpath=//*[normalize-space(text())='Selecciona un idioma para editar']/following::button[1]").first
            if lang not in cur.inner_text():
                cur.click(); self.p.wait_for_timeout(1500)
                self.p.get_by_text(LANG_ES[lang], exact=True).last.click()
        else:
            opt.last.click()
        console.settle(self.p)

    def listing(self):
        self.go("store-listings")
        create = self.p.get_by_role("button", name="Crear ficha de Play Store predeterminada")
        if create.count():   # the API cannot edit the listing until this exists
            create.click()
        else:
            self.go("store-listings/default/edit")
        console.settle(self.p)
        for lang in [self.exp["default_language"]] + [l for l in self.exp["languages"] if l != self.exp["default_language"]]:
            self.select_language(lang)
            console.dismiss_survey(self.p)
            lst = self.app.play / "listing" / lang
            self.p.get_by_role("textbox", name="Nombre de la app").fill((lst / "title.txt").read_text(encoding="utf-8").strip())
            self.p.get_by_role("textbox", name="Descripción breve").fill((lst / "short.txt").read_text(encoding="utf-8").strip())
            self.p.get_by_role("textbox", name="Descripción completa").fill((lst / "full.txt").read_text(encoding="utf-8").strip())
            img = self.app.play / "images" / lang
            for kind in ("icon", "featureGraphic"):
                if self.section_count(IMAGE_SLOTS[kind]) == 0:
                    self.upload(IMAGE_SLOTS[kind], img / f"{kind}.png")
            if self.section_count(IMAGE_SLOTS["phoneScreenshots"]) == 0:
                for f in sorted((img / "phoneScreenshots").glob("*.png")):   # one by one keeps the order
                    self.upload(IMAGE_SLOTS["phoneScreenshots"], f)
            self.save("Guardar como borrador")
            self.shot(f"listing-{lang}")
        self.ai_assets()

    def ai_assets(self):
        ai = self.decl("ai_assets")   # e.g. {"icon": true, "featureGraphic": false, "phoneScreenshots": false}
        self.click("button", "Siguiente", last=True); console.settle(self.p)
        if not any(ai.values()):
            self.p.get_by_text("No etiquetar recursos", exact=True).click()
        else:
            self.p.get_by_text("Etiquetar los recursos como creados o editados con IA", exact=True).click()
            self.click("button", "Etiqueta los recursos generados por IA")
            d = self.p.get_by_role("dialog").last
            for kind, label in IMAGE_SLOTS.items():
                if ai.get(kind):
                    for c in d.get_by_role("checkbox", name=f"{label} - image").all():
                        c.check()
            d.get_by_role("button", name="Etiquetar recursos y enviar").click(); self.p.wait_for_timeout(4000)
        self.save()
        self.shot("listing-ai-assets")

    # --- Closed test -----------------------------------------------------------------------------------
    def closed_test(self):
        self.go("closed-testing")
        self.p.get_by_role("link", name="Administrar segmento Prueba cerrada - Alpha").click(); console.settle(self.p)
        self.p.get_by_role("tab", name="Verificadores").click(); console.settle(self.p)
        lst = self.exp.get("testers_list") or launch.fail("No testers_list in the expediente")
        cb = self.p.get_by_role("checkbox", name=lst)
        if not cb.is_checked():
            cb.check(); self.save()
        self.p.get_by_role("tab", name="Países/regiones").click(); console.settle(self.p)
        add = self.p.get_by_role("button", name="Agregar países o regiones")
        if add.count() and self.exp.get("countries", "all") == "all":
            add.click(); console.settle(self.p)
            self.p.get_by_role("checkbox", name="Seleccionar todas las filas").check()
            self.save()
        self.shot("closed-test")

    def release_notes(self):
        self.go("closed-testing")
        self.p.get_by_role("link", name="Administrar segmento Prueba cerrada - Alpha").click(); console.settle(self.p)
        self.p.get_by_text("Editar versión", exact=True).first.click(); console.settle(self.p)
        ch = self.app.play / "changelogs"
        parts = []
        for lang in self.exp["languages"]:
            f = ch / lang / "default.txt"
            if f.exists():
                parts.append(f"<{lang}>\n{f.read_text(encoding='utf-8').strip()}\n</{lang}>")
        ta = self.p.locator("textarea").first
        ta.fill("\n".join(parts)); ta.press("Tab"); self.p.wait_for_timeout(1500)
        self.click("button", "Siguiente", last=True); console.settle(self.p)
        t = self.p.locator("body").inner_text()
        i = t.find("Errores, advertencias y mensajes")
        print("  release check:", t[i:i + 200].replace("\n", " | "))
        if re.search(r"\d+ error", t[i:i + 200]):
            launch.fail("The release has errors: read the evidence")
        self.save(); self.shot("release-notes")

    def send_review(self):
        ok, why = launch.approval_valid(self.app)
        ok or launch.fail(f"Approval {why}: nothing sent")
        self.go("publishing")
        btn = self.p.get_by_role("button", name=re.compile(r"Enviar \d+ cambios? a revisión"))
        if not btn.count() or not btn.first.is_enabled():
            t = self.p.locator("body").inner_text()
            launch.fail("Cannot send yet: " + t[t.find("Cambios que aún"):][:300].replace("\n", " | "))
        btn.first.click(); self.p.wait_for_timeout(2500)
        self.p.get_by_role("dialog").last.get_by_role("button", name="Envía cambios a revisión").click()
        self.p.wait_for_timeout(8000)
        self.p.reload(wait_until="domcontentloaded"); console.settle(self.p)
        sent = "en proceso de revisión" in self.p.locator("body").inner_text()
        print("  sent for review:", sent)
        self.shot("sent-for-review")
        if sent:
            self.app.set_state("in-review-by-google", "changes sent for review (console_flows send-review)")

    def close(self):
        self.s.close()


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("flow", choices=["all", "declarations", "store-settings", "listing", "closed-test",
                                     "release-notes", "send-review", "pending"])
    ap.add_argument("--app", required=True)
    args = ap.parse_args()
    f = Flow(args.app)
    try:
        steps = {"declarations": f.declarations, "store-settings": f.store_settings, "listing": f.listing,
                 "closed-test": f.closed_test, "release-notes": f.release_notes, "send-review": f.send_review,
                 "pending": f.pending}
        order = ["declarations", "store-settings", "listing", "closed-test", "release-notes", "send-review"]
        for name in (order if args.flow == "all" else [args.flow]):
            print(f"== {name}")
            steps[name]()
    finally:
        f.close()


if __name__ == "__main__":
    main()
