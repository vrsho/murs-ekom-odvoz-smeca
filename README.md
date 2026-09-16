# MURS-EKOM odvoz smeća

Home Assistant integracija za kalendar odvoza [MURS-EKOM](https://murs-ekom.hr/).

**Autor:** Vrsho · **info@vrsho.com**

Prikazuje **kad se što odvozi** i šalje **obavijest s ikonom kante** u satima koje sam podesiš (npr. dan ranije u 18:00).

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/vrsho/murs-ekom-odvoz-smeca/actions/workflows/validate.yml/badge.svg)](https://github.com/vrsho/murs-ekom-odvoz-smeca/actions/workflows/validate.yml)

## Što dobiješ

- izbor **naselja** i **jezika** (System / HR / EN) u postavkama
- automatsko **povlačenje kalendara** (zadano jednom tjedno)
- gumb **Osvježi kalendar** za ručni pull
- senzor **Sljedeći odvoz**
- senzor za svaku vrstu otpada
- binarni senzor **Odvoz danas**
- **kalendar** u Home Assistantu
- obavijesti na telefon (Companion app)
- opcija **Šalji na To-Do listu** (lista **Smeće**)

Vrste otpada: miješani komunalni, bio, plastika i papir, metal/tetrapak/staklo, glomazni, granje, božićna drvca.

## Instalacija

### HACS (preporučeno)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=vrsho&repository=murs-ekom-odvoz-smeca&category=integration)

1. HACS → **⋮** → **Custom repositories**.
2. URL: `https://github.com/vrsho/murs-ekom-odvoz-smeca`
3. Kategorija: **Integration**.
4. **Add** → preuzmi **MURS-EKOM Odvoz smeća**.
5. Restartaj Home Assistant.
6. **Postavke → Uređaji i usluge → Dodaj integraciju** → **MURS-EKOM Odvoz smeća**.

### Ručno

1. Kopiraj mapu `custom_components/murs_ekom` u Home Assistant:

   `config/custom_components/murs_ekom/`

2. Restartaj Home Assistant.
3. **Postavke → Uređaji i usluge → Dodaj integraciju** → **MURS-EKOM Odvoz smeća**.

## Postavke

1. Odaberi **naselje** i **jezik** (zadano System = jezik Home Assistanta).
2. Postavi obavijesti:
   - **Dana prije odvoza:** `1` (dan ranije) ili `0` (na dan odvoza)
   - **Vrijeme:** npr. `18:00:00`
   - **Uređaji:** `notify.mobile_app_tvoj_telefon`
   - **Šalji na To-Do listu:** stvara listu **Smeće** i dodaje stavku u isto vrijeme kao podsjetnik
3. **Razmak povlačenja:** `7` dana (jednom tjedno).

Naselje, interval i obavijesti kasnije mijenjaš na unosu integracije → **Konfiguriraj**.

Za odmah osvježiti kalendar:

- gumb **Osvježi kalendar** na uređaju, ili
- u postavkama uključi **Povuci kalendar sada**, ili
- akcija `murs_ekom.osvjezi`

Test obavijesti: **Alati za razvoj → Akcije → `murs_ekom.test_obavijest`**.

## Napomena o glomaznom otpadu

Glomazni otpad treba **prijaviti** na `040/543-314` najkasnije **2 dana prije** termina.
