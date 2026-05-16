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

## 4. Import / eksport profili taryfowych
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

## 5. Podział kosztów
W trybie porównawczym oraz w cenach bieżących integracja teraz raportuje wszystkie składowe kosztu:
- `energy` – koszt samej energii,
- `variable_fee` – zmienna opłata sieciowa,
- `vat` – podatek VAT dla danej ceny,
- `total` – całkowita cena po doliczeniu opłaty sieciowej i VAT.

Wskaźniki kosztów taryfowych i czujnik rekomendacji korzystają z tych wartości, dzięki czemu możesz porównać nie tylko cenę końcową, ale też strukturę kosztów każdej taryfy.
