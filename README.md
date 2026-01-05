# PGE Dynamic Energy (Ceny Dynamiczne) dla Home Assistant

Integracja pobierająca aktualne ceny energii elektrycznej (Rynek Bilansujący) bezpośrednio z **PGE DataHub**. Narzędzie pozwala na śledzenie cen giełdowych TGE (Towarowa Giełda Energii) w czasie rzeczywistym wewnątrz Home Assistant.

## Główne Funkcje
- **Cena Netto:** Wyświetla czystą stawkę giełdową w **PLN/kWh**.
- **Bezpośrednie źródło:** Dane pobierane z oficjalnego API PGE DataHub.
- **Pełna doba:** 24 odrębne sensory (po jednym na każdą godzinę) + sensor ceny aktualnej.
- **Ikony:** Estetyczne oznaczenia błyskawic (`mdi:lightning-bolt`) ułatwiające orientację w interfejsie.
- **Lekkość:** Minimalne zużycie zasobów dzięki zastosowaniu koordynatora danych (DataUpdateCoordinator).

## Instalacja przez HACS
1. W Home Assistant przejdź do **HACS** -> **Integracje**.
2. Kliknij trzy kropki w prawym górnym rogu i wybierz **Custom repositories** (Niestandardowe repozytoria).
3. Wklej URL tego repozytorium i wybierz kategorię **Integration**.
4. Kliknij **Pobierz**, a następnie zrestartuj Home Assistant.

## Konfiguracja
1. Przejdź do **Ustawienia** -> **Urządzenia oraz usługi**.
2. Kliknij **Dodaj integrację** i wyszukaj `PGE Dynamic Energy`.
3. Wybierz taryfę (np. G1x) i zatwierdź.

## Wykresy (ApexCharts)
Dla najlepszego efektu zaleca się użycie karty `ApexCharts Card` dostępnej w HACS. Pozwala ona na wizualizację cen na całą dobę w formie czytelnego wykresu słupkowego lub liniowego.

## 💡 Masz pomysł? Zgłoś go!
Projekt jest stale rozwijany i jestem otwarty na nowe funkcjonalności! 
- Jeśli masz pomysł na nowy sensor (np. cena średnia, najtańsze godziny),
- Jeśli chcesz zaproponować zmianę w kodzie,
- Jeśli znalazłeś błąd,

**Zgłoś to w sekcji [Issues](https://github.com/AllonGit/ha_pge_dynamic/issues)!** Każda sugestia jest cenna i pomaga ulepszyć integrację dla wszystkich użytkowników.

---
**Nota prawna:** Integracja ma charakter open-source i hobbystyczny. Dane są pobierane z publicznego API PGE. Autor nie ponosi odpowiedzialności za decyzje finansowe podejmowane na podstawie wyświetlanych cen.