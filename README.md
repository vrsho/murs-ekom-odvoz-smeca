# MURS-EKOM odvoz smeća

Home Assistant integracija za kalendar odvoza [MURS-EKOM](https://murs-ekom.hr/).

**Autor:** Vrsho · **info@vrsho.com**

Prikazuje **kad se što odvozi** i šalje **obavijest s ikonom kante** u satima koje sam podesiš (npr. dan ranije u 18:00).

## Što dobiješ

- izbor **naselja** u postavkama
- automatsko **povlačenje kalendara** (zadano jednom tjedno)
- gumb **Osvježi kalendar** za ručni pull
- senzor **Sljedeći odvoz**
- senzor za svaku vrstu otpada
- binarni senzor **Odvoz danas**
- **kalendar** u Home Assistantu
- obavijesti na telefon (Companion app)

Vrste otpada: miješani komunalni, bio, plastika i papir, metal/tetrapak/staklo, glomazni, granje, božićna drvca.

## Instalacija

1. Kopiraj mapu `custom_components/murs_ekom` u Home Assistant:

   `config/custom_components/murs_ekom/`

2. Restartaj Home Assistant.
3. **Postavke → Uređaji i usluge → Dodaj integraciju** → **MURS-EKOM Odvoz smeća**.
4. Odaberi **naselje**.
5. Postavi obavijesti:
   - **Dana prije odvoza:** `1` (dan ranije) ili `0` (na dan odvoza)
   - **Vrijeme:** npr. `18:00:00`
   - **Uređaji:** `notify.mobile_app_tvoj_telefon`
6. **Razmak povlačenja:** `7` dana (jednom tjedno).

Naselje, interval i obavijesti kasnije mijenjaš na unosu integracije → **Konfiguriraj**.

Za odmah osvježiti kalendar:

- gumb **Osvježi kalendar** na uređaju, ili
- u postavkama uključi **Povuci kalendar sada**, ili
- akcija `murs_ekom.osvjezi`

Test obavijesti: **Alati za razvoj → Akcije → `murs_ekom.test_obavijest`**.

## Napomena o glomaznom otpadu

Glomazni otpad treba **prijaviti** na `040/543-314` najkasnije **2 dana prije** termina.
