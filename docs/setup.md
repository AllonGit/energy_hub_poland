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
