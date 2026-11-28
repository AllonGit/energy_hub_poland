# 🛠️ Rozwiązywanie problemów

Zanim zgłosisz błąd, sprawdź poniższe najczęstsze sytuacje.

### ❌ Nie widzę cen energii po instalacji
- **Czekaj na dane:** Ceny RCE są publikowane przez PGEDatahub z opóźnieniem. Pierwsze dane mogą pojawić się po pełnej godzinie.
- **Sprawdź logi:** Przejdź do `Ustawienia -> System -> Logi`. Jeśli widzisz błędy połączenia, sprawdź swoje połączenie internetowe.

### ❓ Cena różni się od tej na fakturze
- **Składniki zmienne:** Upewnij się, że w konfiguracji taryfy G12/G12w podałeś ceny brutto (jeśli takie chcesz widzieć) wraz ze wszystkimi opłatami zmiennymi.
- **Strefy czasowe:** Integracja automatycznie przelicza czas UTC na czas polski. Sprawdź, czy Twój Home Assistant ma poprawnie ustawioną strefę czasową (`Europe/Warsaw`).

### 📊 Nowe sensory nie pokazują się lub są puste
- **Sprawdź tryb pracy:** Sensor `price_status` jest dostępny w trybie dynamicznym oraz w taryfach strefowych G12 i G12w. Sensory typu `best_usage_hour` i `savings_potential` są dostępne w trybie dynamicznym.
- **Poczekaj na dane:** Jeśli nie ma jeszcze pełnego zestawu danych dla dzisiaj lub jutra, niektóre sensory mogą zwracać brak danych.
- **Sprawdź logi:** Jeśli sensor jest zarejestrowany, ale nie ma wartości, sprawdź logi Home Assistant pod kątem błędów związanych z aktualizacją coordinatora.

### 🧪 Brak błędów po aktualizacji, ale integracja nie działa
- **Brak kompilacji:** To jest komponent Pythona, więc nie ma osobnego etapu builda ani kompilacji.
- **Sprawdź logi i testy:** Jeśli pracujesz nad zmianami lokalnie, uruchom `pytest`, aby szybko wykryć problemy z importami lub logiką.

### ⚠️ Błąd "Already configured"
- Możesz posiadać tylko jedną instancję tej integracji. Jeśli chcesz zmienić ustawienia, użyj przycisku **Konfiguruj** na karcie integracji zamiast dodawać ją ponownie.
