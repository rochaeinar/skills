#!/usr/bin/env python3
"""Inventario de un proyecto de app para la revisión profunda del skill app-screen-design.

Lista TODOS los archivos fuente (cada uno con su casilla de revisión) y lo que detecta en cada uno:
pantallas, diálogos, bottom sheets, menús, mensajes, rutas, permisos y fuentes de datos.
Es el mapa de la revisión: no reemplaza leer cada archivo.

Uso: python inventario.py <raíz-del-proyecto> [--out design/cobertura.md]
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

SRC_EXT = {".kt", ".kts", ".java", ".xml", ".dart", ".swift", ".m", ".ts", ".tsx", ".js", ".jsx",
           ".vue", ".svelte", ".json", ".arb", ".gradle", ".sql", ".proto", ".yaml", ".yml", ".md"}
SKIP_DIRS = {"build", ".gradle", ".idea", ".git", "node_modules", ".dart_tool", "Pods", "DerivedData",
             "generated", "intermediates", ".cxx", "dist", ".next", "design", ".claude", "captures"}

# (categoría, regex). Cada coincidencia se anota con su línea.
PATTERNS = [
    ("Pantalla", r"class\s+(\w+)\s*(?:\([^)]*\))?\s*:\s*(?:\w+\.)*(?:AppCompatActivity|ComponentActivity|FragmentActivity|Activity)\b"),
    ("Pantalla", r"class\s+(\w+)\s*(?:\([^)]*\))?\s*:\s*(?:\w+\.)*Fragment\b"),
    ("Pantalla", r"class\s+(\w+)\s+extends\s+(?:AppCompat)?Activity\b"),
    ("Pantalla", r"@Composable\s+(?:\w+\s+)*fun\s+(\w*(?:Screen|Page|Route))\s*\("),
    ("Pantalla", r"class\s+(\w+)\s+extends\s+(?:StatelessWidget|StatefulWidget)"),
    ("Pantalla", r"struct\s+(\w+)\s*:\s*View\b"),
    ("Composable", r"@Composable\s+(?:\w+\s+)*fun\s+(\w+)\s*\("),
    ("Ruta", r"composable\s*\(\s*(?:route\s*=\s*)?[\"']([^\"']+)"),
    ("Ruta", r"<fragment[^>]*android:name=\"([^\"]+)\""),
    ("Ruta", r"GoRoute\s*\([^)]*path:\s*[\"']([^\"']+)"),
    ("Diálogo", r"\b(AlertDialog|DatePickerDialog|TimePickerDialog|ProgressDialog|DialogFragment|BasicAlertDialog|DatePicker|TimePicker)\b"),
    ("Diálogo", r"\b(Dialog)\s*\(\s*onDismissRequest"),
    ("Diálogo", r"\b(showDialog|showDatePicker|\.alert\(|\.confirmationDialog\()"),
    ("Bottom sheet", r"\b(ModalBottomSheet|BottomSheetDialogFragment|BottomSheetScaffold|BottomSheetDialog|showModalBottomSheet|\.sheet\()"),
    ("Menú", r"\b(DropdownMenu|ExposedDropdownMenuBox|PopupMenu|onCreateOptionsMenu|ContextMenu|PopupMenuButton|\.contextMenu)\b"),
    ("Mensaje", r"\b(Snackbar|SnackbarHost|showSnackbar|Toast\.makeText|ScaffoldMessenger)\b"),
    ("Gesto", r"\b(SwipeToDismiss\w*|swipeable|anchoredDraggable|draggable|detectDragGestures|detectTapGestures|pointerInput|combinedClickable|PullToRefresh\w*|SwipeRefreshLayout|ItemTouchHelper|Dismissible|onLongClick)\b"),
    ("Navegación UI", r"\b(NavigationBar|NavigationRail|ModalNavigationDrawer|BottomNavigationView|TabRow|PrimaryTabRow|HorizontalPager|TopAppBar|FloatingActionButton|ExtendedFloatingActionButton)\b"),
    ("Permiso", r"(?:uses-permission[^>]*android:name=\"([^\"]+)\"|Manifest\.permission\.(\w+)|RequestPermission\w*)"),
    ("Datos: entidad", r"@Entity\b|CREATE TABLE\s+(\w+)"),
    ("Datos: DAO", r"@Dao\b|@(Query|Insert|Update|Delete|Upsert)\b"),
    ("Datos: preferencias", r"\b(SharedPreferences|DataStore|preferencesDataStore|stringPreferencesKey|booleanPreferencesKey|intPreferencesKey|UserDefaults|shared_preferences)\b"),
    ("Datos: red", r"@(GET|POST|PUT|DELETE|PATCH)\s*\(|\b(Retrofit|OkHttpClient|HttpClient|Ktor|URLSession|fetch\()"),
    ("Estado", r"\b(StateFlow|MutableStateFlow|LiveData|mutableStateOf|UiState|sealed\s+(?:class|interface)\s+\w*State)\b"),
    ("Lógica", r"class\s+(\w+(?:ViewModel|Repository|UseCase|Service|Worker|Manager|Receiver))\b"),
    ("Monetización", r"\b(AdView|InterstitialAd|RewardedAd|BillingClient|MobileAds)\b"),
    ("Texto fijo", r"Text\s*\(\s*\"[^\"]{3,}\"|android:text=\"[^@\"][^\"]*\""),
]
COMPILED = [(c, re.compile(p)) for c, p in PATTERNS]


def scan(root: Path):
    files, hits = [], defaultdict(list)
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in SRC_EXT:
            continue
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts[:-1]):
            continue
        rel = p.relative_to(root).as_posix()
        if p.suffix == ".json" and "/values" not in rel and not rel.endswith(("strings.json", "en.json")):
            continue  # JSON: solo catálogos de textos
        files.append(rel)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rows = text.splitlines()
        for n, line in enumerate(rows, 1):
            # Une la anotación @Composable de las 2 líneas anteriores para detectar funciones Compose
            prev = " ".join(rows[max(0, n - 3):n - 1])
            if "@Composable" in prev and re.match(r"\s*(?:(?:private|internal|public)\s+)?fun\s", line):
                fn = re.search(r"fun\s+(\w+)", line)
                if fn:
                    cat = "Pantalla" if re.search(r"(Screen|Page|Route)$", fn.group(1)) else "Composable"
                    hits[rel].append((cat, n, fn.group(1)))
                    continue
            for cat, rx in COMPILED:
                m = rx.search(line)
                if m:
                    name = next((g for g in m.groups() if g), m.group(0)) if m.groups() else m.group(0)
                    hits[rel].append((cat, n, name.strip()[:80]))
    return files, hits


def strings_summary(root: Path):
    out = {}
    for p in root.rglob("strings.xml"):
        if any(s in p.parts for s in SKIP_DIRS):
            continue
        n = len(re.findall(r"<(?:string|plurals)\s", p.read_text(encoding="utf-8", errors="replace")))
        out[p.relative_to(root).as_posix()] = n
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    files, hits = scan(root)
    by_cat = defaultdict(list)
    for f, lst in hits.items():
        for cat, n, name in lst:
            by_cat[cat].append(f"`{f}:{n}` {name}")

    lines = [f"# Cobertura de la revisión — {root.name}", "",
             f"**Archivos fuente:** {len(files)} · Revisados: 0 · Marcar `[x]` cada archivo al leerlo COMPLETO y escribir en una línea qué hace.", "",
             "## Resumen detectado", ""]
    order = ["Pantalla", "Ruta", "Diálogo", "Bottom sheet", "Menú", "Mensaje", "Gesto", "Navegación UI",
             "Permiso", "Datos: entidad", "Datos: DAO", "Datos: preferencias", "Datos: red", "Lógica",
             "Monetización", "Texto fijo"]
    for cat in order:
        items = by_cat.get(cat, [])
        lines.append(f"### {cat} ({len(items)})")
        lines += [f"- {i}" for i in items[:300]] or ["- (ninguno detectado: confirmarlo al leer el código)"]
        if len(items) > 300:
            lines.append(f"- … y {len(items) - 300} más")
        lines.append("")
    ss = strings_summary(root)
    if ss:
        lines += ["### Textos (strings.xml)"] + [f"- `{k}`: {v} textos" for k, v in sorted(ss.items())] + [""]

    lines += ["## Archivos (todos)", ""]
    for f in files:
        cats = sorted({c for c, _, _ in hits.get(f, []) if c not in ("Composable", "Estado")})
        tag = f" — detectado: {', '.join(cats)}" if cats else ""
        lines.append(f"- [ ] `{f}`{tag} — ")
    md = "\n".join(lines) + "\n"
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"{len(files)} archivos, {sum(len(v) for v in hits.values())} detecciones -> {out}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(md)


if __name__ == "__main__":
    main()
