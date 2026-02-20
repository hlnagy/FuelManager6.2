# ⛽ Fuel Manager v6.2 - Ultimate User Manual
# ⛽ Fuel Manager v6.2 - Manual de Utilizare
# ⛽ Fuel Manager v6.2 - Felhasználói Kézikönyv

---

## 📑 Cuprins / Tartalomjegyzék / Table of Contents

1.  [🇷🇴 Română](#-română---ghid-complet)
2.  [🇭🇺 Magyar](#-magyar---teljes-útmutató)
3.  [🇬🇧 English](#-english---comprehensive-guide)

---

<a name="-română---ghid-complet"></a>
# 🇷🇴 ROMÂNĂ - Ghid Complet

Bine ați venit în **Fuel Manager v3.1**! 🚀
Aceasta nu este doar o simplă aplicație de gestiune a carburantului. Este un **centru de comandă** complet, proiectat cu pasiune pentru a vă oferi control total, securitate maximă și o experiență vizuală premium. Am pus accent pe detalii, de la animațiile fluide până la protecția datelor din spatele scenei.

## 🌟 1. Interfața și Designul (UI/UX)

Am creat o interfață care "trăiește". Nu este doar statică, ci reacționează la acțiunile dumneavoastră.

*   **Teme Vizuale:**
    *   ☀️ **Luminos (Standard)**: Clar, profesional, ideal pentru birou.
    *   🌙 **Întunecat (Soft)**: Protejează ochii, culori pastelate, contrast perfect.
    *   🪨 **Budila (Rocky)**: O temă exclusivă, robustă, inspirată de balastieră.
*   **Carduri Inteligente:** Pe Dashboard (Panou), cardurile își schimbă culoarea în funcție de stoc.
    *   🟢 **Verde**: Stoc > 15% (Siguranță)
    *   🟡 **Golgalben + Puls**: Stoc > 15% (Siguranță)
    *   🔴 **Roșu + Puls**: Stoc ≤ 15% (Alertă Critică!) – *Nu puteți ignora acest avertisment!*
*   **Feedback Vizual:** Orice acțiune (salvare, ștergere, eroare) este confirmată prin notificări "Toast" elegante sau ferestre modale animate.

## 🛠️ 2. Funcționalități Cheie

### A. Panoul de Control (Dashboard)
Aici aveți pulsul afacerii într-o singură privire:
*   **Capacitate Totală:** Vedeți imediat cât carburant mai aveți în raport cu capacitatea totală a rezervoarelor. Puteți edita această capacitate direct de aici (iconița ✏️).


### B. Gestionare Stoc (Stock)
Inima sistemului. Aici controlați fiecare litru.
*   **Tab-uri Dinamice:** Fiecare firmă are propriul tab colorat automat.
*   **Istoric Detaliat:** Filtrare instantanee, căutare text și...
*   **⚡ OPERAȚIUNI RAPIDE:**
    *   **Intrare:** Alimentarea rezervorului principal.
    *   **Ieșire (Manuală):** Pentru utilaje care nu trec prin pompă sau corecții.
    *   *Secret Feature:* Dacă scrieți un număr de înmatriculare NOU la "Ieșire", sistemul vă anunță cu un badge albastru **"Nou"** și îl creează automat în fundal! Nu mai pierdeți timp cu meniuri de creare!
*   **⚠️ ALIMENTĂRI NEALOCATE:** Un tab special (roșu) apare DOAR dacă există tranzacții orfane. Vă permite să le alocați în masă unei firme corecte.

### C. Rapoarte Avansate (PDF)
Generați documente oficiale cu un singur click.
*   **Bonuri de Consum:** PDF-uri elegante, cu logo-ul firmei, gata de semnat.
*   **Serii Automate:** Sistemul generează automat serii unice pentru fiecare bon (ex: TR-001, VL-054) bazate pe numele firmei.
*   **Calcul Automat:** Selectați perioada și firma -> Sistemul calculează totalul.

### D. Analiză Consum (Efficiency)
Transformăm litrii în bani și eficiență.
*   **Indici de Performanță:** L/km sau L/oră (în funcție de utilaj).
*   **MC (Metri Cubi):** Introduceți producția lunară și vedeți exact câți litri ați consumat per metru cub produs.

## 🛡️ 3. Măsuri de Securitate și "Hidden Features"

Aici este adevărata magie inginerească. Lucrurile pe care nu le vedeți, dar care vă salvează ziua.

1.  **App Data Isolation 🔒:**
    *   Datele NU sunt stocate în `Program Files`. Ele trăiesc în `%LocalAppData%\FuelManager`.
    *   *De ce?* Dacă reinstalați Windows-ul sau programul, datele rămân intacte. Actualizările nu șterg niciodată baza de date!

2.  **Sistemul "Undo/Redo" (Mașina Timpului) ⏪:**
    *   Ați șters o alimentare din greșeală?
    *   Mergeți la Stoc -> Apăsați **Undo**. Gata, a apărut la loc!
    *   V-ați răzgândit? Apăsați **Redo**.
    *   *Tehnic:* Sistemul păstrează un "snapshot" (o copie) a fiecărei înregistrări înainte de modificare.

3.  **Import Robust (Smart Merge) 🔄:**
    *   Când importați un CSV de la pompă, sistemul folosește un algoritm de "diferențiere".
    *   Nu dublează niciodată tranzacțiile! Verifică (Data + Ora + Vehicul + Cantitate). Dacă există deja, o ignoră și vă raportează la final: *"X duplicate găsite"*.

4.  **Heartbeat Monitor ❤️:**
    *   Aplicația rulează un "bătăi de inimă" în fundal. Dacă închideți fereastra browserului, serverul (o consolă neagră) se închide singur după 60 de secunde. Economisește resurse!

5.  **Backup Automat la Import 💾:**
    *   Înainte de a importa o bază de date veche, sistemul face automat o copie de siguranță cu data și ora curentă.
    *   *Locație:* `%LocalAppData%\FuelManager\fuel_manager_v2.db.fixbak_...`

6.  **Log-uri de Debugging 🐞:**
    *   Sistemul scrie tot ce face în fișiere log rotative. Dacă ceva nu merge, un IT-ist poate vedea exact ce s-a întâmplat.

---

<a name="-magyar---teljes-útmutató"></a>
# 🇭🇺 MAGYAR - Teljes Útmutató

Üdvözöljük a **Fuel Manager v3.1**-ban! 🚀
Ez nem csak egy egyszerű üzemanyag-nyilvántartó program. Ez egy **professzionális vezérlőközpont**, amelyet szenvedéllyel terveztünk, hogy teljes ellenőrzést, maximális biztonságot és prémium felhasználói élményt nyújtson.

## 🌟 1. Felület és Design (UI/UX)

Olyan felületet alkottunk, amely "él". Reagál az Ön lépéseire.

*   **Vizuális Témák:**
    *   ☀️ **Világos (Standard)**: Tiszta, átlátható.
    *   🌙 **Sötét (Soft)**: Szemkímélő, pasztell színekkel.
    *   🪨 **Budila (Rocky)**: Egyedi, robusztus, ipari stílusú téma.
*   **Okos Kártyák:** A Vezérlőpulton (Dashboard) a kártyák színe a készlettől függően változik.
    *   🟢 **Zöld**: Készlet > 15% (Biztonságos)
    *   🔴 **Piros + Pulzálás**: Készlet ≤ 15% (Kritikus!) – *Lehetetlen figyelmen kívül hagyni!*
*   **Vizuális Visszajelzés:** Minden műveletet (mentés, törlés) elegáns felugró üzenetek vagy animált ablakok erősítenek meg.

## 🛠️ 2. Főbb Funkciók

### A. Vezérlőpult (Dashboard)
Az üzlet pulzusa egy pillantással:
*   **Teljes Kapacitás:** Azonnal láthatja a készletet a tartályok összkapacitásához viszonyítva. (Szerkeszthető a ✏️ ikonnal).
*   **Fogyasztási Grafikon:** Interaktív grafikon az elmúlt 7 hónap trendjeivel.
*   **Top Fogyasztók:** Automatikus ranglista a legtöbbet fogyasztó járművekről.

### B. Készletkezelés (Stock)
A rendszer szíve.
*   **Dinamikus Fülek:** Minden cégnek saját, színkódolt füle van.
*   **Részletes Előzmények:** Azonnali szűrés, keresés és...
*   **⚡ GYORS MŰVELETEK:**
    *   **Bevét (Intrare):** A főtartály feltöltése.
    *   **Kiadás (Kézi):** Gépekhez, amelyek nem a kútnál tankolnak.
    *   *Titkos Funkció:* Ha egy ÚJ rendszámot ír be a "Kiadás"-hoz, a rendszer kék **"Új"** jelzéssel figyelmeztet, és a háttérben automatikusan létrehozza a járművet! Nem kell a menükben bolyongani!
*   **⚠️ NEM Hozzárendelt (Nealocat):** Egy speciális piros fül, ami CSAK akkor jelenik meg, ha vannak "árva" tranzakciók. Innen csoportosan áthelyezheti őket a megfelelő céghez.

### C. Jelentések (PDF)
Hivatalos dokumentumok egy kattintással.
*   **Fogyasztási Jegyek (Bonuri):** Elegáns PDF, céges logóval, aláírásra kész.
*   **Automatikus Sorozatszám:** A rendszer egyedi sorozatokat generál (pl. TR-001) a cégnév alapján.
*   **Automatikus Számítás:** Válassza ki az időszakot -> A rendszer összegzi a mennyiségeket.

### D. Fogyasztáselemzés (Efficiency)
A litereket pénzzé és hatékonysággá alakítjuk.
*   **Teljesítménymutatók:** L/km vagy L/óra.
*   **MC (Köbméter):** Adja meg a havi termelést, és lássa pontosan, hány liter fogyott egy köbméter termékre.

## 🛡️ 3. Biztonság és "Rejtett Funkciók"

Ez a mérnöki varázslat része. Ami nem látszik, de életmentő lehet.

1.  **Adatizoláció (App Data Isolation) 🔒:**
    *   Az adatok NEM a `Program Files`-ban vannak, hanem a `%LocalAppData%\FuelManager` mappában.
    *   *Miért?* Ha újratelepíti a Windowst vagy a programot, az adatok megmaradnak! A frissítés sosem törli az adatbázist.

2.  **Időgép (Undo/Redo) ⏪:**
    *   Véletlenül törölt egy tankolást?
    *   Menjen a Készletre -> Nyomja meg az **Undo**-t. Visszajött!
    *   Meggondolta magát? Nyomja meg a **Redo**-t.
    *   *Technika:* A rendszer minden módosítás előtt "pillanatfelvételt" készít az adatról.

3.  **Robusztus Import (Smart Merge) 🔄:**
    *   CSV importáláskor a rendszer "intelligens összehasonlítást" végez.
    *   Soha nem duplázza a tranzakciókat! Ellenőrzi (Dátum + Idő + Jármű + Mennyiség). Ha már létezik, átugorja.

4.  **Szívverés Monitor (Heartbeat) ❤️:**
    *   A program a háttérben figyeli az aktivitást. Ha bezárja a böngészőt, a szerver 60 másodperc múlva automatikusan leáll. Erőforrást takarít meg.

5.  **Automatikus Biztonsági Mentés 💾:**
    *   Más adatbázis importálása előtt a rendszer automatikus mentést készít.
    *   *Hely:* `%LocalAppData%\FuelManager\fuel_manager_v2.db.fixbak_...`

---

<a name="-english---comprehensive-guide"></a>
# 🇬🇧 ENGLISH - Comprehensive Guide

Welcome to **Fuel Manager v3.1**! 🚀
This is not just a simple spreadsheet replacement. It is a **professional command center**, passionately designed to offer total control, maximum security, and a premium user experience.

## 🌟 1. Interface & Design (UI/UX)

We created an interface that "lives". It reacts to your actions.

*   **Visual Themes:**
    *   ☀️ **Light (Standard)**: Clean, professional.
    *   🌙 **Dark (Soft)**: Eye-friendly, pastel colors.
    *   🪨 **Budila (Rocky)**: Exclusive robust industrial theme.
*   **Smart Cards:** On the Dashboard, cards change color based on stock levels.
    *   🟢 **Green**: Stock > 15% (Safe)
    *   🔴 **Red + Pulse**: Stock ≤ 15% (Critical Alert!) – *Impossible to ignore!*
*   **Visual Feedback:** Every action (save, delete, error) is confirmed via elegant Toast notifications or animated modals.

## 🛠️ 2. Key Features

### A. Dashboard
Business pulse at a glance:
*   **Total Capacity:** See remaining fuel vs. total tank capacity. Editable inline (✏️ icon).
*   **Consumption Graph:** Interactive chart showing 7-month trends.
*   **Top Consumers:** Auto-generated ranking of highest consumers.

### B. Stock Management
The heart of the system.
*   **Dynamic Tabs:** Each company gets its own auto-colored tab.
*   **History & Filter:** Instant search and filtering.
*   **⚡ QUICK OPERATIONS:**
    *   **In (Intrare):** Refilling the main tank.
    *   **Out (Manual):** For machinery not using the pump.
    *   *Secret Feature:* If you type a NEW license plate in "Out", the system flags it with a blue **"New"** badge and auto-creates the vehicle in the background!
*   **⚠️ UNALLOCATED:** A special red tab appearing ONLY if orphan transactions exist. Allows bulk allocation to the correct company.

### C. Reports (PDF)
Official documents in one click.
*   **Consumption Slips:** Elegant PDFs with company logos.
*   **Auto-Series:** Generates unique ID series (e.g., TR-001) based on company name.
*   **Auto-Calc:** Select period -> System sums it up.

### D. Efficiency Analysis
Turning liters into insights.
*   **KPIs:** L/km or L/hour.
*   **MC (Cubic Meters):** Input monthly production to see Liters per Cubic Meter efficiency.

## 🛡️ 3. Security & Hidden Features

The engineering magic under the hood.

1.  **App Data Isolation 🔒:**
    *   Data lives in `%LocalAppData%\FuelManager`, NOT `Program Files`.
    *   *Why?* Reinstalling Windows or the app keeps data safe. Updates never wipe the DB.

2.  **Time Machine (Undo/Redo) ⏪:**
    *   Accidentally deleted a record?
    *   Go to Stock -> Click **Undo**. It's back!
    *   Changed your mind? Click **Redo**.

3.  **Smart Merge Import 🔄:**
    *   CSV imports use "intelligent diffing".
    *   Never duplicates transactions! Checks (Date + Time + Vehicle + Qty).

4.  **Heartbeat Monitor ❤️:**
    *   Closes backend 60s after browser close to save resources.

5.  **Auto-Backup 💾:**
    *   Creates timestamped backups before risky imports.
    *   *Location:* `%LocalAppData%\FuelManager\fuel_manager_v2.db.fixbak_...`

---
**Fuel Manager v6.2** - *Designed by Nagy H Lajos*
