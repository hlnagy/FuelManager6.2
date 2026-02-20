# 🎨 Dashboard Modernizáció - Útmutató

## ✨ Modern Glassmorphism Dashboard

### Dinamikus Tank Színek (Automatikus)

A főoldali "Panou General" kártya automatikusan változtatja színét a tank töltöttség alapján:

#### 🟢 100-80% - BIZTONSÁGOS (Zöld)
- **Gradient**: Világoszöld → Sötétzöld
- **Jelentés**: Tank majdnem tele, nincs gond

#### 🟡 79-50% - NORMÁL (Sárga)
- **Gradient**: Arany → Mustársárga
- **Jelentés**: Normál üzemelés, minden rendben

#### 🟠 49-30% - FIGYELEM (Narancs)
- **Gradient**: Narancs → Mélynarancs
- **Jelentés**: Figyelj a készletre, nemsokára újratöltés szükséges

#### 🔴 29-20% - ALACSONY (Narancspiros)
- **Gradient**: Narancspiros → Piros
- **Jelentés**: Alacsony készlet, tervezd meg az újratöltést!

#### 🔴 19-0% - **KRITIKUS** (Piros + Animáció)
- **Gradient**: Piros → Bordó
- **Speciális effektusok**:
  - ⚡ Pulzáló ragyogás
  - 📳 Az ikon rezeg
  - 💥 Dinamikus box-shadow
  - 🔔 **FIGYELEM!** Azonnali újratöltés szükséges!

---

## 🪟 Glassmorphism Effektusok

Minden kártya modern üveg (glassmorphism) hatással rendelkezik:

### Vizuális Jellemzők:
- **Elmosott háttér**: `backdrop-filter: blur(20px)`
- **Áttetsző felületek**: `rgba(255, 255, 255, 0.1)`
- **Fényes keretek**: `border: 1px solid rgba(255, 255, 255, 0.2)`
- **Többrétegű árnyékok**: 
  - Külső árnyék: `0 8px 32px rgba(31, 38, 135, 0.15)`
  - Belső fény: `0 0 0 1px rgba(255, 255, 255, 0.1) inset`

### Hover Animációk:
- ✨ Kártyák **felemelkednek** (`translateY(-8px)`)
- 🔍 Kis **nagyítás** (`scale(1.02)`)
- 🌑 **Árnyék növekszik** (`0 20px 60px`)
- ⚡ **Smooth transitions** (`cubic-bezier(0.4, 0, 0.2, 1)`)

---

## 🎯 Használat

### 1. Nyisd meg a Dashboard-ot
Navigálj a főoldalra (Panou Principal)

### 2. Nézd meg a Dinamikus Színeket
A "Panou General" kártya színe **automatikusan beállításra került** a tank töltöttsége alapján:
- Ha a tank **tele** → **Zöld**
- Ha **fogy** → Fokozatosan **Sárga → Narancs → Piros**
- Ha **kritikus** (<20%) → **Pulzáló piros animáció!**

### 3. Hover a Kártyákon
Vidd az egeret a kártyákra és nézd meg az üvegeffektust és az emelkedő animációt!

---

## 🎨 Testreszabás

### Tank Színhatárok Módosítása

Ha módosítani akarod, hogy mely százalékoknál váltson színt a tank:

**Fájl**: `templates/dashboard.html` (a fájl végén, script részben)

```javascript
// Jelenlegi beállítások:
if (tankPercent >= 80) {          // 80% felett → Zöld
    tankCard.classList.add('tank-color-safe');
} else if (tankPercent >= 50) {   // 50-79% → Sárga
    tankCard.classList.add('tank-color-normal');
} else if (tankPercent >= 30) {   // 30-49% → Narancs
    tankCard.classList.add('tank-color-warning');
} else if (tankPercent >= 20) {   // 20-29% → Narancspiros
    tankCard.classList.add('tank-color-low');
} else {                          // 0-19% → KRITIKUS Piros
    tankCard.classList.add('tank-color-critical');
}
```

**Példa**: Ha 70%-nál szeretnéd, hogy sárgába váltson (80% helyett):
```javascript
if (tankPercent >= 70) {  // 70%-ra változtatva
    tankCard.classList.add('tank-color-safe');
}
```

### Színek Módosítása

**Fájl**: `templates/dashboard.html` (style részben)

```css
/* Zöld szín módosítása: */
.tank-color-safe {
    background: linear-gradient(135deg, rgb(34, 197, 94) 0%, rgb(22, 163, 74) 100%) !important;
    /* Változtasd meg az RGB értékeket! */
}

/* Sárga szín módosítása: */
.tank-color-normal {
    background: linear-gradient(135deg, rgb(234, 179, 8) 0%, rgb(202, 138, 4) 100%) !important;
}

/* stb... */
```

### Animáció Sebesség

Kritikus animáció lassítása/gyorsítása:

```css
.tank-color-critical {
    animation: pulse-critical 2s ease-in-out infinite;
    /* 2s → 3s (lassabb), vagy 1s (gyorsabb) */
}
```

### Glassmorphism Blur Erősség

```css
.card-glass {
    backdrop-filter: blur(20px) saturate(180%);
    /* 20px → 10px (kevésbé homályos), vagy 30px (még homályosabb) */
}
```

---

## 📊 Műszaki Részletek

### Fájlok

**`templates/dashboard.html`**
- Glassmorphism CSS stílusok
- Dinamikus színek CSS osztályok
- Tank animációk meghatározása
- JavaScript logika a színváltáshoz

### CSS Osztályok

- `.card-glass` - Üveg effektus
- `.hover-lift` - Hover emelkedés
- `.tank-color-safe` - Zöld (80-100%)
- `.tank-color-normal` - Sárga (50-79%)
- `.tank-color-warning` - Narancs (30-49%)
- `.tank-color-low` - Narancspiros (20-29%)
- `.tank-color-critical` - Piros + animáció (0-19%)
- `.icon-shake` - Ikon rezgés (csak kritikus szintnél)

### Animációk

**`pulse-critical`** - Pulzáló ragyogás kritikus szintnél
- 2 másodperces ciklus
- Box-shadow növekedés/csökkenés
- Scale 1.0 ↔ 1.02

**`icon-shake`** - Ikon rezgés
- 0.5 másodperces ciklus  
- Forgás: 0° → -5° → 5° → 0°

### Browser Kompatibilitás

✅ **Támogatott böngészők:**
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

⚠️ **NEM támogatott:**
- Internet Explorer (glassmorphism nem elérhető)

### Teljesítmény

- **Glassmorphism**: GPU-gyorsított (`backdrop-filter`)
- **Animációk**: `transform` + `opacity` használata (60 FPS)
- **Memóriahasználat**: Minimális (<1MB)
- **CSS méret**: ~3KB (beépítve a dashboard.html-be)

---

## 🚀 Gyors Összefoglaló

1. ✅ **Dashboard megnyitása** → Automatikus színváltás a tank szintjétől függően
2. ✅ **Üvegeffektus** → Modern glassmorphism kártyák
3. ✅ **Hover animációk** → Kártyák emelkednek és nagyobbodnak
4. ✅ **Kritikus figyelmeztetés** → Pulzáló piros animáció 20% alatt

---

## 🎉 Élvezd a modern dizájnt! ✨

**Tipp**: A színek és animációk teljesen testreszabhatók a fenti útmutatók szerint!
