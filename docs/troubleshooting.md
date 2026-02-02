# 🛠️ Rozwiązywanie problemów

Zanim zgłosisz błąd, sprawdź poniższe najczęstsze sytuacje.

### ❌ Nie widzę cen energii po instalacji
- **Czekaj na dane:** Ceny RCE są publikowane przez PGEDatahub z opóźnieniem. Pierwsze dane mogą pojawić się po pełnej godzinie.
- **Sprawdź logi:** Przejdź do `Ustawienia -> System -> Logi`. Jeśli widzisz błędy połączenia, sprawdź swoje połączenie internetowe.

### ❓ Cena różni się od tej na fakturze
- **Składniki zmienne:** Upewnij się, że w konfiguracji taryfy G12/G12w podałeś ceny brutto (jeśli takie chcesz widzieć) wraz ze wszystkimi opłatami zmiennymi.
- **Strefy czasowe:** Integracja automatycznie przelicza czas UTC na czas polski. Sprawdź, czy Twój Home Assistant ma poprawnie ustawioną strefę czasową (`Europe/Warsaw`).

### ⚠️ Błąd "Already configured"
- Możesz posiadać tylko jedną instancję tej integracji. Jeśli chcesz zmienić ustawienia, użyj przycisku **Konfiguruj** na karcie integracji zamiast dodawać ją ponownie.
