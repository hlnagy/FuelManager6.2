# Dashboard Modernizáció - Tervezési Jegyzetek

## Fázis 1: Glassmorphism Dashboard

### Színrendszer - Tank Töltöttség alapján:
- **100-80%**: Zöld (rgb(34, 197, 94)) - Biztonságos
- **79-50%**: Sárga (rgb(234, 179, 8)) - Normál
- **49-30%**: Narancs (rgb(249, 115, 22)) - Figyelem
- **29-20%**: Narancspiros (rgb(239, 68, 68)) - Alacsony
- **19-0%**: Piros (rgb(220, 38, 38)) - Kritikus

### Glassmorphism Elemek:
- `backdrop-filter: blur(10px)`
- `background: rgba(255, 255, 255, 0.1)`
- Border: 1px solid rgba(255, 255, 255, 0.2)
- Box-shadow: több rétegű árnyékok

### Figyelem Felhívó Animációk (<20%):
- Pulzáló animáció
- Ragyogó keret
-Ikon rezgés
- Színes gradient animáció

## Fázis 2: iPhone 17 / iOS Téma

### Betűtípus:
- San Francisco (fallback: -apple-system, BlinkMacSystemFont)

### Színpaletta:
- Primary Blue: #007AFF
- Destructive Red: #FF3B30
- Success Green: #34C759
- Warning Orange: #FF9500
- Gray: #8E8E93
- Background: #F2F2F7 (Light), #000000 (Dark)

### Jellemzők:
- Lekerekített sarkok mindenütt (12-20px)
- Lebegő kártyák
- Smooth transitions (0.3s ease)
- iOS native animációk
- Haptic feedback vizuális szimulációja

