# 🚀 Konfiguracja Energy Hub Poland

Po pomyślnej instalacji przez HACS, wykonaj poniższe kroki, aby w pełni wykorzystać potencjał integracji.

## 1. Dodawanie integracji
1. Przejdź do **Ustawienia** -> **Urządzenia oraz usługi**.
2. Kliknij **Dodaj integrację** i wyszukaj `Energy Hub Poland`.
3. Wybierz preferowany tryb pracy.

## 2. Wybór trybu pracy
- **Taryfa Dynamiczna (RCE):** Pobiera ceny rynkowe energii publikowane przez PSE. Idealne, jeśli rozliczasz się dynamicznie.
- **Wirtualne G12/G12w:** Pozwala na wpisanie stałych stawek Twojego sprzedawcy.
- **Tryb Porównawczy:** Wyświetla dane z taryfy dynamicznej oraz Twoich stawek stałych, pokazując potencjalne oszczędności.

## 3. Integracja z Panelem Energia
Aby widzieć koszty w panelu Energy:
1. Przejdź do **Ustawienia** -> **Tablice rozdzielcze** -> **Energia**.
2. W sekcji "Zużycie energii elektrycznej" wybierz swój sensor zużycia.
3. Wybierz opcję "Użyj encji z ceną energii" i wskaż sensor `sensor.energy_hub_sensor_ceny_aktualnej_twojej_teryfy`.

## 4. Nowe sensory w trybie dynamicznym
Po aktywacji trybu dynamicznego integracja udostępnia dodatkowe sensory, które pomagają w automatyzacjach:
- `price_status` – klasyfikuje bieżącą cenę jako `cheap`, `normal` lub `expensive`.
- `best_usage_hour` – wskazuje najkorzystniejszą godzinę uruchomienia obciążenia.
- `savings_potential` – pokazuje przewidywane oszczędności przy przesunięciu zużycia na najtańszą godzinę.

Przykład automatyzacji:
```yaml
action:
  - service: switch.turn_on
    target:
      entity_id: switch.ladowarka_ev
    condition:
      - condition: state
        entity_id: sensor.energy_hub_status_ceny
        state: cheap
```

## 5. Testy i rozwój lokalny
Jeśli chcesz sprawdzić integrację lokalnie lub rozwijać ją dalej, warto uruchomić testy projektu:

```bash
pytest
```

Komponent jest napisany w Pythonie i jest ładowany przez Home Assistant bez osobnego procesu kompilacji. Najważniejsze jest, aby zachować zgodność z aktualnym API Home Assistant oraz poprawność importów i logiki biznesowej.

## 6. Import / eksport profili taryfowych
Energy Hub Poland obsługuje eksport i import profili taryfowych w formatach **JSON** i **CSV**. Dzięki temu możesz:
- zapisać konfigurację taryfy jako kopię zapasową,
- przenieść ustawienia między instancjami Home Assistanta,
- odtworzyć taryfę bez ręcznego przepisywania wielu wartości.

Aby skorzystać z funkcji, użyj integracyjnych serwisów:
- `service: energy_hub_poland.export_tariff_profile`
- `service: energy_hub_poland.import_tariff_profile`

Przykład eksportu do pliku JSON:
```yaml
service: energy_hub_poland.export_tariff_profile
data:
  path: "energy_hub_poland_profile.json"
```

Przykład importu z pliku CSV:
```yaml
service: energy_hub_poland.import_tariff_profile
data:
  path: "energy_hub_poland_profile.csv"
```

## 7. Podział kosztów
W trybie porównawczym oraz w cenach bieżących integracja teraz raportuje wszystkie składowe kosztu:
- `energy` – koszt samej energii,
- `variable_fee` – zmienna opłata sieciowa,
- `vat` – podatek VAT dla danej ceny,
- `total` – całkowita cena po doliczeniu opłaty sieciowej i VAT.

Wskaźniki kosztów taryfowych i czujnik rekomendacji korzystają z tych wartości, dzięki czemu możesz porównać nie tylko cenę końcową, ale też strukturę kosztów każdej taryfy.
