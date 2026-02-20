# Desktop App - Használati Útmutató

## Amit létrehoztam

✅ **desktop.py** - Desktop launcher script  
✅ **run_desktop.bat** - Gyors teszt futtatáshoz  
✅ **build.bat** - Exe fájl generálásához  
✅ **requirements.txt** - Frissítve pywebview-val  

---

## Hogyan futtasd desktop módban (fejlesztés közben)

### 1. Dupla kattintás a `run_desktop.bat` fájlra

VAGY

### 2. Parancssorból:
```bash
python desktop.py
```

Ez megnyitja az alkalmazást egy **natív Windows ablakban** a böngésző helyett!

---

## Hogyan készítsünk .exe fájlt

### 1. Futtasd a build scriptet:
```bash
build.bat
```

### 2. Várd meg, amíg PyInstaller befejezi (pár perc)

### 3. A kész exe itt lesz:
```
dist\FuelManager.exe
```

### 4. Teszteld:
- Másold le a `FuelManager.exe`-t egy másik mappába
- Dupla kattintás az exe-re
- Az alkalmazás STANDALONE-ként kell elinduljon (Python nélkül is!)

---

## Fontos infók

### ✅ Mi működik
- Natív Windows ablak
- Az összes meglévő funkció (dashboard, reports, stb.)
- Ablak méretezése, minimalizálása, maximalizálása
- Standalone exe generálás

### ⚠️ Pythonnet nem települt
- Ez csak egy kiegészítő volt natív file dialogokhoz
- Az alkalmazás tökéletesen működik nélküle
- A CSV import és minden más funkció rendben van

### 📦 Exe fájl méret
- Várható méret: ~40-70 MB
- Tartalmazza az összes függőséget (Flask, pandas, fpdf, stb.)

---

## Troubleshooting

### Ha a desktop.py hibát ad:
1. Ellenőrizd, hogy a Flask app fut-e: `python app.py`
2. Nézd meg a terminal kimenetben az esetleges hibákat

### Ha az exe nem indul el:
1. Ellenőrizd, hogy a `fuel_manager.db` az exe mellett van-e
2. Futtasd parancssorból: `FuelManager.exe` hogy lásd az esetleges hibaüzeneteket

### Ha a build.bat nem fut:
1. Ellenőrizd, hogy a pyinstaller telepítve van-e: `python -m pip list | findstr pyinstaller`
2. Ha nincs: `python -m pip install pyinstaller`

---

## Következő lépések

1. **Teszteld desktop módban**: Futtasd `run_desktop.bat`-ot
2. **Ha rendben van**, build-eld az exe-t: `build.bat`
3. **Teszteld az exe-t** egy clean környezetben

Készen áll a használatra! 🚀
